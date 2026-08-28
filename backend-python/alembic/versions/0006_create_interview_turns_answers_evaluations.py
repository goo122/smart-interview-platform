"""create interview turns, answers and evaluations

Revision ID: 0006_turns_answers_evaluations
Revises: 0005_create_interview_tables
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_turns_answers_evaluations"
down_revision: str | None = "0005_create_interview_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "interview_turns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=True),
        sa.Column("parent_turn_id", sa.Uuid(), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("turn_type", sa.String(length=16), nullable=False),
        sa.Column("question_content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("follow_up_depth", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("follow_up_depth >= 0", name="ck_interview_turns_follow_up_depth"),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["interview_questions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["parent_turn_id"], ["interview_turns.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "sequence", name="uq_interview_turns_session_sequence"),
    )
    op.create_index(
        "ix_interview_turns_session_status_sequence",
        "interview_turns",
        ["session_id", "status", "sequence"],
    )

    op.create_table(
        "interview_answers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("turn_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["turn_id"], ["interview_turns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("turn_id", name="uq_interview_answers_turn"),
        sa.UniqueConstraint(
            "session_id", "request_id", name="uq_interview_answers_session_request"
        ),
    )
    op.create_index(
        "ix_interview_answers_session_created_at",
        "interview_answers",
        ["session_id", "created_at"],
    )

    op.create_table(
        "interview_evaluations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("turn_id", sa.Uuid(), nullable=False),
        sa.Column("overall_score", sa.Integer(), nullable=False),
        sa.Column("technical_score", sa.Integer(), nullable=False),
        sa.Column("relevance_score", sa.Integer(), nullable=False),
        sa.Column("clarity_score", sa.Integer(), nullable=False),
        sa.Column("depth_score", sa.Integer(), nullable=False),
        sa.Column("strengths", sa.JSON(), nullable=False),
        sa.Column("weaknesses", sa.JSON(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("suggested_improvements", sa.JSON(), nullable=False),
        sa.Column("llm_should_follow_up", sa.Boolean(), nullable=False),
        sa.Column("follow_up_focus", sa.String(length=500), nullable=True),
        sa.Column("follow_up_question", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "overall_score BETWEEN 0 AND 100", name="ck_interview_evaluations_overall_score"
        ),
        sa.CheckConstraint(
            "technical_score BETWEEN 0 AND 100", name="ck_interview_evaluations_technical_score"
        ),
        sa.CheckConstraint(
            "relevance_score BETWEEN 0 AND 100", name="ck_interview_evaluations_relevance_score"
        ),
        sa.CheckConstraint(
            "clarity_score BETWEEN 0 AND 100", name="ck_interview_evaluations_clarity_score"
        ),
        sa.CheckConstraint(
            "depth_score BETWEEN 0 AND 100", name="ck_interview_evaluations_depth_score"
        ),
        sa.ForeignKeyConstraint(["turn_id"], ["interview_turns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("turn_id", name="uq_interview_evaluations_turn"),
    )
    op.create_index(
        "ix_interview_evaluations_turn_created_at",
        "interview_evaluations",
        ["turn_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_interview_evaluations_turn_created_at", table_name="interview_evaluations"
    )
    op.drop_table("interview_evaluations")
    op.drop_index("ix_interview_answers_session_created_at", table_name="interview_answers")
    op.drop_table("interview_answers")
    op.drop_index(
        "ix_interview_turns_session_status_sequence", table_name="interview_turns"
    )
    op.drop_table("interview_turns")
