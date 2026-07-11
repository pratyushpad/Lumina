"""Initial schema: sessions, documents, messages, chunks (pgvector + tsvector)

Revision ID: 0001
Revises:
Create Date: 2026-07-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("stored_path", sa.String(), nullable=False),
        sa.Column("file_type", sa.String(), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), server_default="0"),
        sa.Column("num_pages", sa.Integer(), nullable=True),
        sa.Column("num_chunks", sa.Integer(), server_default="0"),
        sa.Column("has_images", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("status", sa.String(), nullable=False, server_default="processing"),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", JSONB(), nullable=True),
        sa.Column("model_used", sa.String(), nullable=True),
        sa.Column("retrieval_time_ms", sa.Integer(), nullable=True),
        sa.Column("generation_time_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "chunks",
        sa.Column("chunk_id", sa.String(), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("page_num", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("block_type", sa.String(), nullable=False, server_default="text"),
        sa.Column("filename", sa.String(), nullable=False, server_default=""),
        sa.Column(
            "has_associated_image", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("image_path", sa.String(), nullable=True),
        sa.Column("chunking_strategy", sa.String(), nullable=False, server_default="recursive"),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "tsv",
            TSVECTOR(),
            sa.Computed("to_tsvector('english', text)", persisted=True),
        ),
        sa.Column("embedding", Vector(EMBEDDING_DIM)),
    )

    op.create_index("chunks_doc_idx", "chunks", ["document_id"])
    op.execute(
        "CREATE INDEX chunks_embedding_hnsw_idx ON chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute("CREATE INDEX chunks_tsv_idx ON chunks USING gin (tsv)")


def downgrade() -> None:
    op.drop_table("chunks")
    op.drop_table("messages")
    op.drop_table("documents")
    op.drop_table("sessions")
