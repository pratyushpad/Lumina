import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Document, Message, Session
from app.schemas.session import (
    SessionCreate,
    SessionListResponse,
    SessionRename,
    SessionResponse,
)
from app.services.retrieval.sparse import BM25Index
from app.services.vectorstore.pgvector import PgVectorStore
from app.utils.file_handler import cleanup_document_files, rmtree_safe

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


async def _to_response(db: AsyncSession, s: Session) -> SessionResponse:
    doc_count = await db.scalar(
        select(func.count(Document.id)).where(Document.session_id == s.id)
    )
    msg_count = await db.scalar(
        select(func.count(Message.id)).where(Message.session_id == s.id)
    )
    return SessionResponse(
        id=s.id,
        name=s.name,
        created_at=s.created_at,
        updated_at=s.updated_at,
        document_count=doc_count or 0,
        message_count=msg_count or 0,
    )


@router.post("/", response_model=SessionResponse)
async def create_session(body: SessionCreate, db: AsyncSession = Depends(get_db)):
    s = Session(name=body.name or "New Session")
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return await _to_response(db, s)


@router.get("/", response_model=SessionListResponse)
async def list_sessions(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Session).order_by(Session.updated_at.desc()))
    sessions = res.scalars().all()
    items = [await _to_response(db, s) for s in sessions]
    return SessionListResponse(sessions=items, total=len(items))


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    s = await db.get(Session, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    return await _to_response(db, s)


@router.patch("/{session_id}", response_model=SessionResponse)
async def rename_session(
    session_id: str, body: SessionRename, db: AsyncSession = Depends(get_db)
):
    s = await db.get(Session, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    s.name = body.name
    await db.commit()
    await db.refresh(s)
    return await _to_response(db, s)


@router.delete("/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    s = await db.get(Session, session_id)
    if not s:
        raise HTTPException(404, "Session not found")

    # Cascade vectors + files
    docs_res = await db.execute(select(Document).where(Document.session_id == session_id))
    docs = docs_res.scalars().all()
    store = PgVectorStore.get()
    for d in docs:
        await store.delete_by_document_id(d.id)
        BM25Index.get().invalidate(d.id)
        cleanup_document_files(d.stored_path, d.id, settings.PROCESSED_DIR)

    # Remove session-scoped upload dir
    session_upload_dir = os.path.join(settings.UPLOAD_DIR, session_id)
    rmtree_safe(session_upload_dir)

    await db.delete(s)
    await db.commit()
    return {"message": "Session deleted", "session_id": session_id}
