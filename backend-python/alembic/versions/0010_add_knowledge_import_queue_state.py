"""add durable knowledge import queue state"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010_knowledge_queue_state"
down_revision: str | None = "0009_resume_report_snapshot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_documents",
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("failure_code", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("failure_message", sa.Text(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE knowledge_documents "
            "SET queued_at = created_at "
            "WHERE queued_at IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE knowledge_documents "
            "SET failure_code = error_code, failure_message = error_message "
            "WHERE failure_code IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("knowledge_documents", "failure_message")
    op.drop_column("knowledge_documents", "failure_code")
    op.drop_column("knowledge_documents", "attempt_count")
    op.drop_column("knowledge_documents", "processing_started_at")
    op.drop_column("knowledge_documents", "queued_at")
