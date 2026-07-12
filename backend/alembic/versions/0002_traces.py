"""Query traces: per-stage candidates, scores, and latencies

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "traces",
        sa.Column("trace_id", sa.String(), primary_key=True),
        sa.Column(
            "message_id",
            sa.String(),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column("session_id", sa.String(), nullable=True, index=True),
        sa.Column("query", sa.String(), nullable=False),
        sa.Column("total_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("tokens_per_sec", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "trace_stages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "trace_id",
            sa.String(),
            sa.ForeignKey("traces.trace_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("trace_stages")
    op.drop_table("traces")
