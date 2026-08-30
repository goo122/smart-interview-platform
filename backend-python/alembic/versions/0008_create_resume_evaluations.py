"""add traceable resume match evaluations

Revision ID: 0008_resume_evaluations
Revises: 0007_interview_reports
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_resume_evaluations"
down_revision: str | None = "0007_interview_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "interview_resume_evaluations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_base_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("overall_score", sa.Integer(), nullable=True),
        sa.Column("skills_match_score", sa.Integer(), nullable=True),
        sa.Column("experience_match_score", sa.Integer(), nullable=True),
        sa.Column("evidence_quality_score", sa.Integer(), nullable=True),
        sa.Column("clarity_score", sa.Integer(), nullable=True),
        sa.Column("strengths", sa.JSON(), nullable=False),
        sa.Column("gaps", sa.JSON(), nullable=False),
        sa.Column("suggestions", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source_document_ids", sa.JSON(), nullable=False),
        sa.Column("evaluation_version", sa.String(length=64), nullable=False),
        sa.Column("provider_name", sa.String(length=64), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING', 'EVALUATING', 'COMPLETED', 'FAILED', 'UNAVAILABLE')",
            name="ck_interview_resume_evaluations_status",
        ),
        sa.CheckConstraint(
            "overall_score IS NULL OR overall_score BETWEEN 0 AND 100",
            name="ck_interview_resume_evaluations_overall_score",
        ),
        sa.CheckConstraint(
            "skills_match_score IS NULL OR skills_match_score BETWEEN 0 AND 100",
            name="ck_interview_resume_evaluations_skills_score",
        ),
        sa.CheckConstraint(
            "experience_match_score IS NULL OR experience_match_score BETWEEN 0 AND 100",
            name="ck_interview_resume_evaluations_experience_score",
        ),
        sa.CheckConstraint(
            "evidence_quality_score IS NULL OR evidence_quality_score BETWEEN 0 AND 100",
            name="ck_interview_resume_evaluations_evidence_score",
        ),
        sa.CheckConstraint(
            "clarity_score IS NULL OR clarity_score BETWEEN 0 AND 100",
            name="ck_interview_resume_evaluations_clarity_score",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["interview_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id"], ["knowledge_bases.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", name="uq_interview_resume_evaluations_session"),
    )
    op.create_index(
        "ix_interview_resume_evaluations_user_status_updated_at",
        "interview_resume_evaluations",
        ["user_id", "status", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_interview_resume_evaluations_user_status_updated_at",
        table_name="interview_resume_evaluations",
    )
    op.drop_table("interview_resume_evaluations")
