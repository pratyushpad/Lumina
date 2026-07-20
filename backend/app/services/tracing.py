"""Per-query pipeline tracing: every stage records its candidates, scores, and latency.

A Tracer is created per request, threaded through the retrieval pipeline, fed the
generation result, then flushed once to Postgres and linked to the assistant message.
Answering "why did this query return that chunk" is a table lookup, not archaeology.
"""
import logging
import time
from contextlib import contextmanager
from typing import Any

from app.database import AsyncSessionLocal
from app.models.trace import Trace, TraceStage

logger = logging.getLogger("lumina.tracing")


class Tracer:
    def __init__(self, query: str, session_id: str | None = None):
        self.query = query
        self.session_id = session_id
        self._t0 = time.perf_counter()
        self._stages: list[tuple[str, int, Any]] = []
        self.provider: str | None = None
        self.model: str | None = None
        self.tokens_per_sec: float | None = None

    def stage(self, name: str, latency_ms: int, payload: Any = None) -> None:
        self._stages.append((name, latency_ms, payload))

    @contextmanager
    def timed(self, name: str, payload_fn=None):
        """Context manager: times the block, records the stage on exit.
        payload_fn (optional) is called AFTER the block to build the payload."""
        t0 = time.perf_counter()
        holder: dict = {}
        try:
            yield holder
        finally:
            ms = int((time.perf_counter() - t0) * 1000)
            payload = payload_fn() if payload_fn else holder.get("payload")
            self.stage(name, ms, payload)

    def set_generation(self, provider: str, model: str, tokens_per_sec: float) -> None:
        self.provider = provider
        self.model = model
        self.tokens_per_sec = tokens_per_sec

    async def flush(self, message_id: str | None = None) -> str:
        total_ms = int((time.perf_counter() - self._t0) * 1000)
        trace = Trace(
            message_id=message_id,
            session_id=self.session_id,
            query=self.query,
            total_ms=total_ms,
            provider=self.provider,
            model=self.model,
            tokens_per_sec=self.tokens_per_sec,
        )
        trace.stages = [
            TraceStage(seq=i, stage=name, latency_ms=ms, payload=payload)
            for i, (name, ms, payload) in enumerate(self._stages)
        ]
        try:
            async with AsyncSessionLocal() as db:
                db.add(trace)
                await db.commit()
                return trace.trace_id
        except Exception:
            logger.exception("Failed to flush trace (non-fatal)")
            return ""


def candidates_payload(items: list[tuple[str, float]], limit: int = 20) -> dict:
    """Standard payload shape for a ranked-candidates stage."""
    return {
        "count": len(items),
        "top": [{"chunk_id": cid, "score": round(score, 5)} for cid, score in items[:limit]],
    }
