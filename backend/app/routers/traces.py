"""Query-trace inspection API: the full pipeline record behind any assistant message."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Trace

router = APIRouter(prefix="/api/traces", tags=["traces"])


def _to_dict(t: Trace) -> dict:
    return {
        "trace_id": t.trace_id,
        "message_id": t.message_id,
        "session_id": t.session_id,
        "query": t.query,
        "total_ms": t.total_ms,
        "provider": t.provider,
        "model": t.model,
        "tokens_per_sec": t.tokens_per_sec,
        "created_at": t.created_at.isoformat(),
        "stages": [
            {
                "seq": s.seq,
                "stage": s.stage,
                "latency_ms": s.latency_ms,
                "payload": s.payload,
            }
            for s in t.stages
        ],
    }


@router.get("/{message_id}")
async def get_trace(message_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Trace).where(Trace.message_id == message_id))
    trace = res.scalars().first()
    if not trace:
        raise HTTPException(404, "No trace for this message")
    return _to_dict(trace)
