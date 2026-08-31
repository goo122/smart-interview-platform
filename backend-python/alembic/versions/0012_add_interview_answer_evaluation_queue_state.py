"""add durable interview answer evaluation queue state"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012_interview_answer_eval_queue"
down_revision: str | None = "0011_interview_preparation_queue"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "interview_turns",
        sa.Column("evaluation_queued_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "interview_turns",
        sa.Column("evaluation_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "interview_turns",
        sa.Column("evaluation_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "interview_turns",
        sa.Column(
            "evaluation_attempt_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "interview_turns",
        sa.Column("evaluation_failure_code", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "interview_turns",
        sa.Column("evaluation_failure_message", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_interview_turns_evaluation_recovery",
        "interview_turns",
        ["status", "evaluation_started_at", "evaluation_attempt_count"],
    )


def downgrade() -> None:
    op.drop_index("ix_interview_turns_evaluation_recovery", table_name="interview_turns")
    op.drop_column("interview_turns", "evaluation_failure_message")
    op.drop_column("interview_turns", "evaluation_failure_code")
    op.drop_column("interview_turns", "evaluation_attempt_count")
    op.drop_column("interview_turns", "evaluation_completed_at")
    op.drop_column("interview_turns", "evaluation_started_at")
    op.drop_column("interview_turns", "evaluation_queued_at")
