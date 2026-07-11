from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    GEMINI_API_KEY: str = ""
    DATABASE_URL: str = "postgresql+asyncpg://lumina:lumina@localhost:5433/lumina"
    UPLOAD_DIR: str = "./storage/uploads"
    PROCESSED_DIR: str = "./storage/processed"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 384
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Ingestion
    CHUNKING_STRATEGY: str = "recursive"  # fixed | recursive | semantic
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 150

    # Retrieval pipeline defaults (per-request overridable via RetrievalConfig)
    RETRIEVAL_MODE: str = "hybrid_rrf"  # dense | sparse | hybrid_rrf
    SPARSE_METHOD: str = "bm25"  # bm25 (true BM25, in-process) | fts (Postgres ts_rank_cd)
    QUERY_TRANSFORM: str = "none"  # none | multi_query | hyde
    RRF_K: int = 60
    TOP_K_CANDIDATES: int = 50
    TOP_K_RERANKED: int = 5

    LLM_MODEL: str = "gemini-2.5-flash"
    LLM_MAX_TOKENS: int = 2048
    # slowapi rate limits (per IP)
    RATE_LIMIT_CHAT: str = "20/minute"
    RATE_LIMIT_UPLOAD: str = "10/minute"
    RATE_LIMIT_DEFAULT: str = "60/minute"
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: list[str] = [".pdf", ".txt", ".md", ".png", ".jpg", ".jpeg"]


settings = Settings()
