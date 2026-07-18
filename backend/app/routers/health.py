import time
from datetime import datetime

from fastapi import APIRouter, Response
from sqlalchemy import text

from app.database import engine
from app.services.embedding.embedder import EmbeddingService
from app.services.retrieval.reranker import Reranker
from app.services.vectorstore.pgvector import PgVectorStore

router = APIRouter(tags=["health"])

_started_at = time.monotonic()


@router.get("/health")
async def health():
    # Liveness only — must stay DB-free so external keep-warm pingers don't
    # burn managed-Postgres compute hours or mask DB outages as app outages.
    return {
        "status": "ok",
        "uptime_s": round(time.monotonic() - _started_at, 1),
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/health/ready")
async def ready(response: Response):
    services = {"db": False, "vectorstore": False, "embedder": False, "reranker": False}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        services["db"] = True
    except Exception:
        pass
    try:
        await PgVectorStore.get().get_stats()
        services["vectorstore"] = True
    except Exception:
        pass
    try:
        services["embedder"] = EmbeddingService.get().dimension > 0
    except Exception:
        pass
    try:
        services["reranker"] = Reranker.get().model is not None
    except Exception:
        pass
    ok = all(services.values())
    if not ok:
        response.status_code = 503
    return {
        "status": "ready" if ok else "degraded",
        "services": services,
        "timestamp": datetime.utcnow().isoformat(),
    }
