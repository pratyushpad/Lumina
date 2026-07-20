"""The chat turn, owned in one place.

A turn is always: resolve documents → retrieve (+vision enrich) → confidence
gate → build prompt → generate → persist user+assistant → flush trace. The
blocking endpoint and the SSE endpoint differ only in how generation is
consumed and how the result reaches the client, so everything else lives here
rather than being written twice in the router.
"""
import json
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Document, Message, Session
from app.schemas.chat import Citation
from app.services.generation.llm import LLMService
from app.services.generation.prompt_builder import PromptBuilder
from app.services.guardrails.confidence import REFUSAL_MESSAGE, should_refuse
from app.services.multimodal.vision import VisionService
from app.services.retrieval.pipeline import RetrievalPipeline
from app.services.retrieval.types import RetrievalResult
from app.services.tracing import Tracer

logger = logging.getLogger("lumina.chat")

REFUSAL_LABEL = "guardrail:refusal"
# Shown to the client when a turn fails. Details go to the logs only — the SSE
# path must not echo internals any more than the JSON error handler does.
STREAM_ERROR_MESSAGE = "Something went wrong generating that answer. Please try again."


@dataclass
class Turn:
    """State shared by both transports once retrieval has run."""

    query: str
    session_id: str
    tracer: Tracer
    chunks: list[RetrievalResult]
    retrieval_ms: int
    citations: list[Citation] = field(default_factory=list)


def to_citation(r: RetrievalResult) -> Citation:
    return Citation(
        chunk_id=r.chunk_id,
        document_id=r.document_id,
        filename=r.filename,
        page_num=r.page_num,
        chunk_text=r.text[:1000],
        relevance_score=r.relevance_score,
        has_image=r.has_associated_image,
        image_path=r.image_path,
    )


class ChatService:
    async def document_ids_for_session(self, db: AsyncSession, session_id: str) -> list[str]:
        res = await db.execute(
            select(Document.id).where(
                Document.session_id == session_id, Document.status == "ready"
            )
        )
        return [row[0] for row in res.all()]

    async def resolve_documents(self, db: AsyncSession, session_id: str) -> list[str]:
        """Validate the session has ingested documents, or raise the API error."""
        sess = await db.get(Session, session_id)
        if not sess:
            raise HTTPException(404, "Session not found")
        document_ids = await self.document_ids_for_session(db, session_id)
        if not document_ids:
            raise HTTPException(400, "No ready documents in this session")
        return document_ids

    async def retrieve(self, query: str, session_id: str, document_ids: list[str]) -> Turn:
        tracer = Tracer(query, session_id=session_id)
        t0 = time.time()
        results = await RetrievalPipeline().run(query, document_ids, tracer=tracer)
        if any(r.has_associated_image for r in results):
            tv = time.time()
            results = await VisionService.get().enrich_retrieval_results(results, query)
            tracer.stage(
                "vision_enrich",
                int((time.time() - tv) * 1000),
                {"enriched": [r.chunk_id for r in results if r.has_associated_image]},
            )
        turn = Turn(
            query=query,
            session_id=session_id,
            tracer=tracer,
            chunks=results,
            retrieval_ms=int((time.time() - t0) * 1000),
        )
        turn.citations = [to_citation(c) for c in results]
        return turn

    def should_refuse(self, turn: Turn) -> bool:
        if not should_refuse(turn.chunks, turn.query):
            return False
        top = max((c.relevance_score for c in turn.chunks), default=0.0)
        turn.tracer.stage(
            "refusal",
            0,
            {"top_rerank_score": round(top, 4), "threshold": settings.MIN_RERANK_SCORE},
        )
        return True

    def build_prompt(self, turn: Turn) -> tuple[str, str]:
        builder = PromptBuilder()
        return (
            builder.build_system_prompt(),
            builder.build_user_prompt(turn.query, turn.chunks),
        )

    async def persist_turn(
        self,
        turn: Turn,
        answer: str,
        model_used: str,
        gen_ms: int,
        citations: list[Citation] | None = None,
    ) -> str:
        """Write the user+assistant pair and flush the trace. Returns message id.

        Uses its own DB session deliberately: on the streaming path the
        request-scoped session is long gone by the time generation finishes.
        """
        cites = turn.citations if citations is None else citations
        async with AsyncSessionLocal() as db:
            sess = await db.get(Session, turn.session_id)
            asst_msg = Message(
                session_id=turn.session_id,
                role="assistant",
                content=answer,
                citations=[c.model_dump() for c in cites],
                model_used=model_used,
                retrieval_time_ms=turn.retrieval_ms,
                generation_time_ms=gen_ms,
            )
            db.add_all(
                [
                    Message(session_id=turn.session_id, role="user", content=turn.query),
                    asst_msg,
                ]
            )
            if sess:
                sess.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(asst_msg)
            message_id = asst_msg.id
        await turn.tracer.flush(message_id=message_id)
        return message_id

    def _record_generation(self, turn: Turn, result, gen_ms: int) -> None:
        turn.tracer.stage(
            "generation",
            gen_ms,
            {
                "provider": result.provider,
                "model": result.model,
                "completion_tokens": result.completion_tokens,
                "tokens_per_sec": round(result.tokens_per_sec, 1),
            },
        )
        turn.tracer.set_generation(result.provider, result.model, result.tokens_per_sec)

    async def answer(self, query: str, session_id: str, document_ids: list[str]):
        """Blocking turn. Returns (message_id, content, citations, retrieval_ms,
        gen_ms, model_used) for the router to shape into a ChatResponse."""
        turn = await self.retrieve(query, session_id, document_ids)

        if self.should_refuse(turn):
            message_id = await self.persist_turn(
                turn, REFUSAL_MESSAGE, REFUSAL_LABEL, 0, citations=[]
            )
            return message_id, REFUSAL_MESSAGE, [], turn.retrieval_ms, 0, REFUSAL_LABEL

        system, user = self.build_prompt(turn)
        result = await LLMService.get().generate_result(system, user)
        gen_ms = int(result.duration_s * 1000)
        self._record_generation(turn, result, gen_ms)
        message_id = await self.persist_turn(turn, result.text, result.label, gen_ms)
        return (
            message_id,
            result.text,
            turn.citations,
            turn.retrieval_ms,
            gen_ms,
            result.label,
        )

    async def stream(
        self, query: str, session_id: str, document_ids: list[str]
    ) -> AsyncIterator[dict]:
        """Streaming turn, yielding SSE payloads (citations/token/meta/refusal/done)."""

        def event(kind: str, data) -> dict:
            return {"data": json.dumps({"type": kind, "data": data})}

        try:
            turn = await self.retrieve(query, session_id, document_ids)

            if self.should_refuse(turn):
                yield event("refusal", REFUSAL_MESSAGE)
                message_id = await self.persist_turn(
                    turn, REFUSAL_MESSAGE, REFUSAL_LABEL, 0, citations=[]
                )
                yield event("done", {"message_id": message_id})
                return

            yield event("citations", [c.model_dump() for c in turn.citations])

            system, user = self.build_prompt(turn)
            parts: list[str] = []
            gen_result = None
            async for ev in LLMService.get().generate_stream_events(system, user):
                if isinstance(ev, str):
                    parts.append(ev)
                    yield event("token", ev)
                else:
                    gen_result = ev

            gen_ms = int(gen_result.duration_s * 1000) if gen_result else 0
            model_label = gen_result.label if gen_result else settings.LLM_MODEL
            if gen_result:
                self._record_generation(turn, gen_result, gen_ms)
                yield event(
                    "meta",
                    {
                        "provider": gen_result.provider,
                        "model": gen_result.model,
                        "tokens_per_sec": round(gen_result.tokens_per_sec, 1),
                        "completion_tokens": gen_result.completion_tokens,
                        "tokens_estimated": gen_result.tokens_estimated,
                        "generation_time_ms": gen_ms,
                    },
                )

            message_id = await self.persist_turn(
                turn, "".join(parts), model_label, gen_ms
            )
            yield event("done", {"message_id": message_id})
        except Exception:
            logger.exception("Stream failure")
            yield event("error", STREAM_ERROR_MESSAGE)
