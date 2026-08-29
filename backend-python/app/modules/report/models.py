from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class InterviewReportModel(Base):
    __tablename__ = "interview_reports"
    __table_args__ = (
        UniqueConstraint("session_id", name="uq_interview_reports_session"),
        Index("ix_interview_reports_user_status_updated_at", "user_id", "status", "updated_at"),
        CheckConstraint(
            "status IN ('PENDING', 'GENERATING', 'READY', 'FAILED')",
            name="ck_interview_reports_status",
        ),
        CheckConstraint(
            "overall_score BETWEEN 0 AND 100", name="ck_interview_reports_overall_score"
        ),
        CheckConstraint(
            "technical_score BETWEEN 0 AND 100", name="ck_interview_reports_technical_score"
        ),
        CheckConstraint(
            "relevance_score BETWEEN 0 AND 100", name="ck_interview_reports_relevance_score"
        ),
        CheckConstraint(
            "clarity_score BETWEEN 0 AND 100", name="ck_interview_reports_clarity_score"
        ),
        CheckConstraint(
            "depth_score BETWEEN 0 AND 100", name="ck_interview_reports_depth_score"
        ),
        CheckConstraint(
            "generated_by IN ('RULES', 'LLM', 'HYBRID')",
            name="ck_interview_reports_generated_by",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("interview_sessions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    technical_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    relevance_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clarity_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    depth_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resume_evaluation_snapshot: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    radar_data: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    strengths: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    weaknesses: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    suggested_improvements: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    action_plan: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    recommended_level: Mapped[str | None] = mapped_column(String(100), nullable=True)
    aggregation_version: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    generated_by: Mapped[str] = mapped_column(String(16), nullable=False, default="RULES")
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InterviewReportItemModel(Base):
    __tablename__ = "interview_report_items"
    __table_args__ = (
        UniqueConstraint("report_id", "sequence", name="uq_interview_report_items_report_sequence"),
        Index("ix_interview_report_items_report_sequence", "report_id", "sequence"),
        CheckConstraint(
            "overall_score BETWEEN 0 AND 100", name="ck_interview_report_items_overall_score"
        ),
        CheckConstraint(
            "technical_score BETWEEN 0 AND 100", name="ck_interview_report_items_technical_score"
        ),
        CheckConstraint(
            "relevance_score BETWEEN 0 AND 100", name="ck_interview_report_items_relevance_score"
        ),
        CheckConstraint(
            "clarity_score BETWEEN 0 AND 100", name="ck_interview_report_items_clarity_score"
        ),
        CheckConstraint(
            "depth_score BETWEEN 0 AND 100", name="ck_interview_report_items_depth_score"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    report_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("interview_reports.id", ondelete="CASCADE"), nullable=False
    )
    turn_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    parent_turn_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    turn_type: Mapped[str] = mapped_column(String(16), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)
    technical_score: Mapped[int] = mapped_column(Integer, nullable=False)
    relevance_score: Mapped[int] = mapped_column(Integer, nullable=False)
    clarity_score: Mapped[int] = mapped_column(Integer, nullable=False)
    depth_score: Mapped[int] = mapped_column(Integer, nullable=False)
    strengths: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    weaknesses: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    feedback: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_improvements: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
