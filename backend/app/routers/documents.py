import logging
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal, get_db
from app.middleware.rate_limit import limiter
from app.models import Document, Session
from app.schemas.document import (
    DocumentDeleteResponse,
    DocumentListItem,
    DocumentStatusResponse,
    DocumentUploadResponse,
)
from app.services.embedding.embedder import EmbeddingService
from app.services.ingestion.extractor import IngestionPipeline
from app.services.multimodal.vision import VisionService
from app.services.retrieval.sparse import BM25Index
from app.services.vectorstore.pgvector import PgVectorStore
from app.utils.file_handler import (
    cleanup_document_files,
    get_file_extension,
    get_file_type,
    save_upload_file,
)

router = APIRouter(prefix="/api/documents", tags=["documents"])
logger = logging.getLogger("lumina.documents")


async def _process_document_bg(
    document_id: str, stored_path: str, filename: str, file_type: str
):
    """Background task: parse → chunk → embed → store → update DB row."""
    pipeline = IngestionPipeline()
    embedder = EmbeddingService.get()
    store = PgVectorStore.get()

    async with AsyncSessionLocal() as db:
        try:
            parse_result, chunks = await pipeline.process(
                stored_path, document_id, file_type, filename
            )

            # For image-only chunks, enrich with vision description before embedding
            if file_type == "image" and parse_result.extracted_images:
                vision = VisionService.get()
                for c in chunks:
                    if c.has_associated_image and c.image_path:
                        desc = await vision.describe_image(c.image_path)
                        if desc:
                            c.text = f"{c.text}\n\n{desc}"

            if chunks:
                vectors = embedder.embed_texts([c.text for c in chunks])
                await store.add_chunks(chunks, vectors)
                BM25Index.get().invalidate(document_id)

            doc = await db.get(Document, document_id)
            if doc:
                doc.status = "ready"
                doc.num_chunks = len(chunks)
                doc.num_pages = parse_result.num_pages
                doc.has_images = parse_result.has_images
                doc.processed_at = datetime.utcnow()
                await db.commit()
            logger.info("Processed document %s: %d chunks", document_id, len(chunks))
        except Exception as e:
            logger.exception("Failed to process document %s", document_id)
            doc = await db.get(Document, document_id)
            if doc:
                doc.status = "error"
                doc.error_message = str(e)[:500]
                await db.commit()


@router.post("/upload", response_model=DocumentUploadResponse)
@limiter.limit(settings.RATE_LIMIT_UPLOAD)
async def upload_document(
    request: Request,
    background: BackgroundTasks,
    session_id: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    sess = await db.get(Session, session_id)
    if not sess:
        raise HTTPException(404, "Session not found")

    ext = get_file_extension(file.filename or "")
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File extension {ext} not allowed")

    file_type = get_file_type(file.filename or "")
    if file_type == "unknown":
        raise HTTPException(400, "Unsupported file type")

    document_id = str(uuid.uuid4())
    stored_filename = f"{document_id}_{file.filename}"
    stored_path = os.path.join(settings.UPLOAD_DIR, session_id, stored_filename)
    bytes_written = await save_upload_file(file, stored_path)

    if bytes_written > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        os.remove(stored_path)
        raise HTTPException(413, f"File exceeds {settings.MAX_FILE_SIZE_MB} MB limit")

    doc = Document(
        id=document_id,
        session_id=session_id,
        filename=file.filename or stored_filename,
        stored_path=stored_path,
        file_type=file_type,
        file_size_bytes=bytes_written,
        status="processing",
    )
    db.add(doc)
    await db.commit()

    background.add_task(_process_document_bg, document_id, stored_path, doc.filename, file_type)

    return DocumentUploadResponse(
        document_id=document_id,
        filename=doc.filename,
        status="processing",
        num_chunks=0,
        num_pages=None,
        has_images=False,
        message="Document accepted for processing",
    )


@router.get("/session/{session_id}", response_model=list[DocumentListItem])
async def list_documents(session_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(Document).where(Document.session_id == session_id).order_by(Document.uploaded_at.desc())
    )
    return list(res.scalars().all())


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_status(document_id: str, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return DocumentStatusResponse(
        document_id=doc.id,
        status=doc.status,
        num_chunks=doc.num_chunks or 0,
        error_message=doc.error_message,
    )


@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(document_id: str, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    chunks_deleted = await PgVectorStore.get().delete_by_document_id(document_id)
    BM25Index.get().invalidate(document_id)
    cleanup_document_files(doc.stored_path, doc.id, settings.PROCESSED_DIR)
    await db.delete(doc)
    await db.commit()
    return DocumentDeleteResponse(
        document_id=document_id,
        message="Document deleted",
        chunks_deleted=chunks_deleted,
    )
