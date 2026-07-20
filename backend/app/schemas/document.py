from datetime import datetime

from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    num_chunks: int = 0
    num_pages: int | None = None
    has_images: bool = False
    message: str


class DocumentListItem(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size_bytes: int
    num_chunks: int
    status: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


class DocumentStatusResponse(BaseModel):
    document_id: str
    status: str
    num_chunks: int
    error_message: str | None = None


class DocumentDeleteResponse(BaseModel):
    document_id: str
    message: str
    chunks_deleted: int
