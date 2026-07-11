from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import text

from app.database import engine
from app.services.embedding.embedder import EmbeddingService
from app.services.vectorstore.pgvector import PgVectorStore

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    services = {"vectorstore": False, "db": False, "embedder": False}
    try:
        await PgVectorStore.get().get_stats()
        services["vectorstore"] = True
    except Exception:
        pass
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        services["db"] = True
    except Exception:
        pass
    try:
        services["embedder"] = EmbeddingService.get().dimension > 0
    except Exception:
        pass
    return {
        "status": "ok" if all(services.values()) else "degraded",
        "services": services,
        "timestamp": datetime.utcnow().isoformat(),
    }
