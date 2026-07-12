import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class Trace(Base):
    __tablename__ = "traces"

    trace_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(
        String, ForeignKey("messages.id", ondelete="CASCADE"), nullable=True, index=True
    )
    session_id = Column(String, nullable=True, index=True)
    query = Column(String, nullable=False)
    total_ms = Column(Integer, nullable=False, default=0)
    provider = Column(String, nullable=True)
    model = Column(String, nullable=True)
    tokens_per_sec = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    stages = relationship(
        "TraceStage", back_populates="trace", cascade="all, delete-orphan",
        lazy="selectin", order_by="TraceStage.seq",
    )


class TraceStage(Base):
    __tablename__ = "trace_stages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trace_id = Column(
        String, ForeignKey("traces.trace_id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq = Column(Integer, nullable=False)
    stage = Column(String, nullable=False)
    latency_ms = Column(Integer, nullable=False, default=0)
    payload = Column(JSONB, nullable=True)

    trace = relationship("Trace", back_populates="stages")
