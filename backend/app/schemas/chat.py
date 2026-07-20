from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    stream: bool = True


class Citation(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    page_num: int | None = None
    chunk_text: str
    relevance_score: float
    has_image: bool = False
    image_path: str | None = None


class ChatResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    message_id: str
    content: str
    citations: list[Citation]
    retrieval_time_ms: int
    generation_time_ms: int
    model_used: str


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: str
    role: str
    content: str
    citations: list[Citation] | None = None
    model_used: str | None = None
    created_at: datetime


class StreamChunk(BaseModel):
    type: str
    data: Any = None
