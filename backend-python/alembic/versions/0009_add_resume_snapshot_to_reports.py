"""store immutable resume evaluation snapshot in reports

Revision ID: 0009_resume_report_snapshot
Revises: 0008_resume_evaluations
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009_resume_report_snapshot"
down_revision: str | None = "0008_resume_evaluations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "interview_reports",
        sa.Column("resume_evaluation_snapshot", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("interview_reports", "resume_evaluation_snapshot")
