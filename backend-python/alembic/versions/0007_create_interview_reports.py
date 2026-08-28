"""create immutable interview reports and replay items

Revision ID: 0007_interview_reports
Revises: 0006_turns_answers_evaluations
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_interview_reports"
down_revision: str | None = "0006_turns_answers_evaluations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "interview_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("overall_score", sa.Integer(), nullable=False),
        sa.Column("technical_score", sa.Integer(), nullable=False),
        sa.Column("relevance_score", sa.Integer(), nullable=False),
        sa.Column("clarity_score", sa.Integer(), nullable=False),
        sa.Column("depth_score", sa.Integer(), nullable=False),
        sa.Column("radar_data", sa.JSON(), nullable=False),
        sa.Column("strengths", sa.JSON(), nullable=False),
        sa.Column("weaknesses", sa.JSON(), nullable=False),
        sa.Column("suggested_improvements", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("action_plan", sa.JSON(), nullable=False),
        sa.Column("recommended_level", sa.String(length=100), nullable=True),
        sa.Column("aggregation_version", sa.String(length=32), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=True),
        sa.Column("generated_by", sa.String(length=16), nullable=False),
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
            "status IN ('PENDING', 'GENERATING', 'READY', 'FAILED')",
            name="ck_interview_reports_status",
        ),
        sa.CheckConstraint(
            "overall_score BETWEEN 0 AND 100", name="ck_interview_reports_overall_score"
        ),
        sa.CheckConstraint(
            "technical_score BETWEEN 0 AND 100", name="ck_interview_reports_technical_score"
        ),
        sa.CheckConstraint(
            "relevance_score BETWEEN 0 AND 100", name="ck_interview_reports_relevance_score"
        ),
        sa.CheckConstraint(
            "clarity_score BETWEEN 0 AND 100", name="ck_interview_reports_clarity_score"
        ),
        sa.CheckConstraint(
            "depth_score BETWEEN 0 AND 100", name="ck_interview_reports_depth_score"
        ),
        sa.CheckConstraint(
            "generated_by IN ('RULES', 'LLM', 'HYBRID')",
            name="ck_interview_reports_generated_by",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["interview_sessions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", name="uq_interview_reports_session"),
    )
    op.create_index(
        "ix_interview_reports_user_status_updated_at",
        "interview_reports",
        ["user_id", "status", "updated_at"],
    )

    op.create_table(
        "interview_report_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("turn_id", sa.Uuid(), nullable=False),
        sa.Column("parent_turn_id", sa.Uuid(), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("turn_type", sa.String(length=16), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("overall_score", sa.Integer(), nullable=False),
        sa.Column("technical_score", sa.Integer(), nullable=False),
        sa.Column("relevance_score", sa.Integer(), nullable=False),
        sa.Column("clarity_score", sa.Integer(), nullable=False),
        sa.Column("depth_score", sa.Integer(), nullable=False),
        sa.Column("strengths", sa.JSON(), nullable=False),
        sa.Column("weaknesses", sa.JSON(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("suggested_improvements", sa.JSON(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "overall_score BETWEEN 0 AND 100", name="ck_interview_report_items_overall_score"
        ),
        sa.CheckConstraint(
            "technical_score BETWEEN 0 AND 100", name="ck_interview_report_items_technical_score"
        ),
        sa.CheckConstraint(
            "relevance_score BETWEEN 0 AND 100", name="ck_interview_report_items_relevance_score"
        ),
        sa.CheckConstraint(
            "clarity_score BETWEEN 0 AND 100", name="ck_interview_report_items_clarity_score"
        ),
        sa.CheckConstraint(
            "depth_score BETWEEN 0 AND 100", name="ck_interview_report_items_depth_score"
        ),
        sa.ForeignKeyConstraint(
            ["report_id"], ["interview_reports.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "report_id", "sequence", name="uq_interview_report_items_report_sequence"
        ),
    )
    op.create_index(
        "ix_interview_report_items_report_sequence",
        "interview_report_items",
        ["report_id", "sequence"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_interview_report_items_report_sequence", table_name="interview_report_items"
    )
    op.drop_table("interview_report_items")
    op.drop_index(
        "ix_interview_reports_user_status_updated_at", table_name="interview_reports"
    )
    op.drop_table("interview_reports")
