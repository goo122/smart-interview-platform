"""add durable interview report generation queue state"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013_interview_report_queue"
down_revision: str | None = "0012_interview_answer_eval_queue"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "interview_reports",
        sa.Column("generation_queued_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "interview_reports",
        sa.Column("generation_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "interview_reports",
        sa.Column("generation_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "interview_reports",
        sa.Column("generation_attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "interview_reports",
        sa.Column("generation_lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "interview_reports",
        sa.Column("generation_fencing_token", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_interview_report_items_report_turn",
        "interview_report_items",
        ["report_id", "turn_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_interview_report_items_report_turn",
        "interview_report_items",
        type_="unique",
    )
    op.drop_column("interview_reports", "generation_fencing_token")
    op.drop_column("interview_reports", "generation_lease_expires_at")
    op.drop_column("interview_reports", "generation_attempt_count")
    op.drop_column("interview_reports", "generation_completed_at")
    op.drop_column("interview_reports", "generation_started_at")
    op.drop_column("interview_reports", "generation_queued_at")
