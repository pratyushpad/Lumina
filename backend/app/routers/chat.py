import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.database import AsyncSessionLocal, get_db
from app.middleware.rate_limit import limiter
from app.models import Message
from app.schemas.chat import ChatRequest, ChatResponse, MessageResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger("lumina.chat")


@router.post("/{session_id}", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_CHAT)
async def chat(
    request: Request, session_id: str, body: ChatRequest, db: AsyncSession = Depends(get_db)
):
    service = ChatService()
    document_ids = await service.resolve_documents(db, session_id)
    (
        message_id,
        content,
        citations,
        retrieval_ms,
        gen_ms,
        model_used,
    ) = await service.answer(body.query, session_id, document_ids)
    return ChatResponse(
        message_id=message_id,
        content=content,
        citations=citations,
        retrieval_time_ms=retrieval_ms,
        generation_time_ms=gen_ms,
        model_used=model_used,
    )


@router.get("/{session_id}/stream")
@limiter.limit(settings.RATE_LIMIT_CHAT)
async def chat_stream(request: Request, session_id: str, query: str):
    service = ChatService()
    # Validate session + docs before opening the stream, so failures surface as
    # a normal HTTP error rather than an SSE error event.
    async with AsyncSessionLocal() as db:
        document_ids = await service.resolve_documents(db, session_id)
    return EventSourceResponse(service.stream(query, session_id, document_ids))


@router.get("/{session_id}/history", response_model=list[MessageResponse])
async def history(session_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at.asc())
    )
    return list(res.scalars().all())
