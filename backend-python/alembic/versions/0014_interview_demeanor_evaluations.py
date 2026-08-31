"""store image-free interview demeanor evaluation samples"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014_demeanor_evaluation"
down_revision: str | Sequence[str] | None = "0013_interview_report_queue"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "interview_demeanor_evaluations",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("session_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("overall_score", sa.Integer(), nullable=False),
        sa.Column("eye_contact_score", sa.Integer(), nullable=False),
        sa.Column("posture_score", sa.Integer(), nullable=False),
        sa.Column("facial_visibility_score", sa.Integer(), nullable=False),
        sa.Column("expression_naturalness_score", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("suggestions", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("provider_name", sa.String(length=64), nullable=False),
        sa.Column("analysis_version", sa.String(length=64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "overall_score BETWEEN 0 AND 100",
            name="ck_interview_demeanor_evaluations_overall_score",
        ),
        sa.CheckConstraint(
            "eye_contact_score BETWEEN 0 AND 100",
            name="ck_interview_demeanor_evaluations_eye_contact_score",
        ),
        sa.CheckConstraint(
            "posture_score BETWEEN 0 AND 100",
            name="ck_interview_demeanor_evaluations_posture_score",
        ),
        sa.CheckConstraint(
            "facial_visibility_score BETWEEN 0 AND 100",
            name="ck_interview_demeanor_evaluations_facial_visibility_score",
        ),
        sa.CheckConstraint(
            "expression_naturalness_score BETWEEN 0 AND 100",
            name="ck_interview_demeanor_evaluations_expression_score",
        ),
        sa.CheckConstraint(
            "confidence BETWEEN 0 AND 100",
            name="ck_interview_demeanor_evaluations_confidence",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["interview_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_interview_demeanor_evaluations_session_captured_at",
        "interview_demeanor_evaluations",
        ["session_id", "captured_at"],
    )
    op.create_index(
        "ix_interview_demeanor_evaluations_user_session_captured_at",
        "interview_demeanor_evaluations",
        ["user_id", "session_id", "captured_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_interview_demeanor_evaluations_user_session_captured_at",
        table_name="interview_demeanor_evaluations",
    )
    op.drop_index(
        "ix_interview_demeanor_evaluations_session_captured_at",
        table_name="interview_demeanor_evaluations",
    )
    op.drop_table("interview_demeanor_evaluations")
