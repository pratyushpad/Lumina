from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Column, Computed, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR

from app.config import settings
from app.database import Base


class Chunk(Base):
    __tablename__ = "chunks"

    chunk_id = Column(String, primary_key=True)
    document_id = Column(
        String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index = Column(Integer, nullable=False, default=0)
    page_num = Column(Integer, nullable=False, default=0)
    block_type = Column(String, nullable=False, default="text")
    filename = Column(String, nullable=False, default="")
    has_associated_image = Column(Boolean, nullable=False, default=False)
    image_path = Column(String, nullable=True)
    chunking_strategy = Column(String, nullable=False, default="recursive")
    text = Column(Text, nullable=False)
    tsv = Column(TSVECTOR, Computed("to_tsvector('english', text)", persisted=True))
    embedding = Column(Vector(settings.EMBEDDING_DIM))
