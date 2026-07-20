"""Shared retrieval data types (kept free of any vector-store implementation)."""
from dataclasses import dataclass


@dataclass
class RetrievalResult:
    chunk_id: str
    document_id: str
    text: str
    page_num: int
    filename: str
    distance: float
    has_associated_image: bool = False
    image_path: str | None = None
    relevance_score: float = 0.0
    block_type: str = "text"
