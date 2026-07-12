import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler

from app.config import settings
from app.middleware.error_handler import register_error_handlers
from app.middleware.rate_limit import limiter
from app.migrations import run_migrations
from app.routers import chat, config as config_router, documents, health, sessions, traces
from app.services.embedding.embedder import EmbeddingService
from app.services.retrieval.reranker import Reranker
from app.services.vectorstore.pgvector import PgVectorStore
from app.utils.file_handler import ensure_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("lumina")


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dir(settings.UPLOAD_DIR)
    ensure_dir(os.path.join(settings.PROCESSED_DIR, "images"))
    await run_migrations()
    EmbeddingService.get()
    Reranker.get()
    PgVectorStore.get()
    logger.info("Lumina backend ready")
    yield


app = FastAPI(title="Lumina API", version="1.0.0", lifespan=lifespan)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

app.include_router(health.router)
app.include_router(config_router.router)
app.include_router(sessions.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(traces.router)

images_path = os.path.join(settings.PROCESSED_DIR, "images")
ensure_dir(images_path)
app.mount("/static/images", StaticFiles(directory=images_path), name="images")
