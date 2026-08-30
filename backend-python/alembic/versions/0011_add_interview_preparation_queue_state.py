"""add durable interview preparation queue state"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011_interview_preparation_queue"
down_revision: str | None = "0010_knowledge_queue_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "interview_sessions",
        sa.Column("preparation_queued_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "interview_sessions",
        sa.Column("preparation_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "interview_sessions",
        sa.Column(
            "preparation_attempt_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.execute(
        sa.text(
            "UPDATE interview_sessions "
            "SET preparation_queued_at = created_at "
            "WHERE preparation_queued_at IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE interview_sessions "
            "SET preparation_started_at = updated_at "
            "WHERE status = 'PREPARING' AND preparation_started_at IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("interview_sessions", "preparation_attempt_count")
    op.drop_column("interview_sessions", "preparation_started_at")
    op.drop_column("interview_sessions", "preparation_queued_at")
