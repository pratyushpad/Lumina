import json
import logging
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.database import AsyncSessionLocal, get_db
from app.middleware.rate_limit import limiter
from app.models import Document, Message, Session
from app.schemas.chat import ChatRequest, ChatResponse, Citation, MessageResponse
from app.services.generation.llm import LLMService
from app.services.generation.prompt_builder import PromptBuilder
from app.services.multimodal.vision import VisionService
from app.services.retrieval.pipeline import RetrievalPipeline
from app.services.retrieval.types import RetrievalResult

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger("lumina.chat")


async def _document_ids_for_session(db: AsyncSession, session_id: str) -> list[str]:
    res = await db.execute(
        select(Document.id).where(
            Document.session_id == session_id, Document.status == "ready"
        )
    )
    return [row[0] for row in res.all()]


def _to_citation(r: RetrievalResult) -> Citation:
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


async def _run_retrieval(
    query: str, document_ids: list[str]
) -> tuple[list[RetrievalResult], int]:
    t0 = time.time()
    results = await RetrievalPipeline().run(query, document_ids)
    if any(r.has_associated_image for r in results):
        results = await VisionService.get().enrich_retrieval_results(results, query)
    elapsed = int((time.time() - t0) * 1000)
    return results, elapsed


@router.post("/{session_id}", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_CHAT)
async def chat(request: Request, session_id: str, body: ChatRequest, db: AsyncSession = Depends(get_db)):
    sess = await db.get(Session, session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    document_ids = await _document_ids_for_session(db, session_id)
    if not document_ids:
        raise HTTPException(400, "No ready documents in this session")

    chunks, retrieval_ms = await _run_retrieval(body.query, document_ids)
    builder = PromptBuilder()
    system = builder.build_system_prompt()
    user = builder.build_user_prompt(body.query, chunks)

    t0 = time.time()
    text, _ = await LLMService.get().generate(system, user)
    gen_ms = int((time.time() - t0) * 1000)

    citations = [_to_citation(c) for c in chunks]

    # Persist user + assistant
    user_msg = Message(session_id=session_id, role="user", content=body.query)
    asst_msg = Message(
        session_id=session_id,
        role="assistant",
        content=text,
        citations=[c.model_dump() for c in citations],
        model_used=settings.LLM_MODEL,
        retrieval_time_ms=retrieval_ms,
        generation_time_ms=gen_ms,
    )
    db.add_all([user_msg, asst_msg])
    sess.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(asst_msg)

    return ChatResponse(
        message_id=asst_msg.id,
        content=text,
        citations=citations,
        retrieval_time_ms=retrieval_ms,
        generation_time_ms=gen_ms,
        model_used=settings.LLM_MODEL,
    )


@router.get("/{session_id}/stream")
@limiter.limit(settings.RATE_LIMIT_CHAT)
async def chat_stream(request: Request, session_id: str, query: str):
    # Validate session + docs synchronously before opening the stream
    async with AsyncSessionLocal() as db:
        sess = await db.get(Session, session_id)
        if not sess:
            raise HTTPException(404, "Session not found")
        document_ids = await _document_ids_for_session(db, session_id)
    if not document_ids:
        raise HTTPException(400, "No ready documents in this session")

    async def event_gen():
        try:
            chunks, retrieval_ms = await _run_retrieval(query, document_ids)
            citations = [_to_citation(c) for c in chunks]
            yield {
                "data": json.dumps(
                    {"type": "citations", "data": [c.model_dump() for c in citations]}
                )
            }

            builder = PromptBuilder()
            system = builder.build_system_prompt()
            user = builder.build_user_prompt(query, chunks)

            t0 = time.time()
            full_text_parts: list[str] = []
            async for token in LLMService.get().generate_stream(system, user):
                full_text_parts.append(token)
                yield {"data": json.dumps({"type": "token", "data": token})}
            gen_ms = int((time.time() - t0) * 1000)
            full_text = "".join(full_text_parts)

            # Persist messages
            async with AsyncSessionLocal() as db:
                sess = await db.get(Session, session_id)
                user_msg = Message(session_id=session_id, role="user", content=query)
                asst_msg = Message(
                    session_id=session_id,
                    role="assistant",
                    content=full_text,
                    citations=[c.model_dump() for c in citations],
                    model_used=settings.LLM_MODEL,
                    retrieval_time_ms=retrieval_ms,
                    generation_time_ms=gen_ms,
                )
                db.add_all([user_msg, asst_msg])
                if sess:
                    sess.updated_at = datetime.utcnow()
                await db.commit()

            yield {"data": json.dumps({"type": "done", "data": None})}
        except Exception as e:
            logger.exception("Stream failure")
            yield {"data": json.dumps({"type": "error", "data": str(e)})}

    return EventSourceResponse(event_gen())


@router.get("/{session_id}/history", response_model=list[MessageResponse])
async def history(session_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at.asc())
    )
    return list(res.scalars().all())
