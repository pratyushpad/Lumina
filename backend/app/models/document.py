import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(
        String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename = Column(String, nullable=False)
    stored_path = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    file_size_bytes = Column(Integer, default=0)
    num_pages = Column(Integer, nullable=True)
    num_chunks = Column(Integer, default=0)
    has_images = Column(Boolean, default=False)
    status = Column(String, default="processing", nullable=False)
    error_message = Column(String, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)

    session = relationship("Session", back_populates="documents")
