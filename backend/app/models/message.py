import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(
        String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    citations = Column(JSONB, nullable=True)
    model_used = Column(String, nullable=True)
    retrieval_time_ms = Column(Integer, nullable=True)
    generation_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    session = relationship("Session", back_populates="messages")
