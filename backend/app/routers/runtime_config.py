from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["config"])


@router.get("/api/config")
async def get_config():
    return {
        "model": settings.LLM_MODEL,
        "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
        "allowed_extensions": settings.ALLOWED_EXTENSIONS,
        "top_k_reranked": settings.TOP_K_RERANKED,
    }
