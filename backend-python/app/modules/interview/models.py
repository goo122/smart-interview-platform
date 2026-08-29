from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
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


class InterviewSessionModel(Base):
    __tablename__ = "interview_sessions"
    __table_args__ = (
        UniqueConstraint("user_id", "request_id", name="uq_interview_sessions_user_request"),
        Index("ix_interview_sessions_user_updated_at", "user_id", "updated_at"),
        Index("ix_interview_sessions_user_status", "user_id", "status"),
        CheckConstraint(
            "question_count >= 3 AND question_count <= 20",
            name="ck_interview_sessions_question_count",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    knowledge_base_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="RESTRICT"), nullable=False
    )
    job_title: Mapped[str] = mapped_column(String(200), nullable=False)
    job_description: Mapped[str] = mapped_column(Text, nullable=False)
    interview_type: Mapped[str] = mapped_column(String(32), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(16), nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="CREATED")
    current_question_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    prepared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InterviewResumeEvaluationModel(Base):
    """One immutable-source evaluation record per interview session."""

    __tablename__ = "interview_resume_evaluations"
    __table_args__ = (
        UniqueConstraint("session_id", name="uq_interview_resume_evaluations_session"),
        Index(
            "ix_interview_resume_evaluations_user_status_updated_at",
            "user_id",
            "status",
            "updated_at",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'EVALUATING', 'COMPLETED', 'FAILED', 'UNAVAILABLE')",
            name="ck_interview_resume_evaluations_status",
        ),
        CheckConstraint(
            "overall_score IS NULL OR overall_score BETWEEN 0 AND 100",
            name="ck_interview_resume_evaluations_overall_score",
        ),
        CheckConstraint(
            "skills_match_score IS NULL OR skills_match_score BETWEEN 0 AND 100",
            name="ck_interview_resume_evaluations_skills_score",
        ),
        CheckConstraint(
            "experience_match_score IS NULL OR experience_match_score BETWEEN 0 AND 100",
            name="ck_interview_resume_evaluations_experience_score",
        ),
        CheckConstraint(
            "evidence_quality_score IS NULL OR evidence_quality_score BETWEEN 0 AND 100",
            name="ck_interview_resume_evaluations_evidence_score",
        ),
        CheckConstraint(
            "clarity_score IS NULL OR clarity_score BETWEEN 0 AND 100",
            name="ck_interview_resume_evaluations_clarity_score",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    knowledge_base_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    skills_match_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    experience_match_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clarity_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    strengths: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    gaps: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    suggestions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_document_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    evaluation_version: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InterviewQuestionModel(Base):
    __tablename__ = "interview_questions"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence", name="uq_interview_questions_session_sequence"),
        Index("ix_interview_questions_session_sequence", "session_id", "sequence"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(16), nullable=False)
    expected_points: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    source_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class InterviewEventModel(Base):
    __tablename__ = "interview_events"
    __table_args__ = (
        Index("ix_interview_events_session_created_at", "session_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    to_status: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class InterviewQuestionCitationModel(Base):
    __tablename__ = "interview_question_citations"
    __table_args__ = (
        UniqueConstraint(
            "question_id", "chunk_id", name="uq_interview_question_citations_question_chunk"
        ),
        Index("ix_interview_question_citations_question_ordinal", "question_id", "ordinal"),
        CheckConstraint("score >= 0 AND score <= 1", name="ck_interview_question_citations_score"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    question_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("interview_questions.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("knowledge_chunks.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[str] = mapped_column(String(16), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class InterviewTurnModel(Base):
    __tablename__ = "interview_turns"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence", name="uq_interview_turns_session_sequence"),
        Index("ix_interview_turns_session_status_sequence", "session_id", "status", "sequence"),
        CheckConstraint("follow_up_depth >= 0", name="ck_interview_turns_follow_up_depth"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("interview_questions.id", ondelete="SET NULL"), nullable=True
    )
    parent_turn_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("interview_turns.id", ondelete="SET NULL"), nullable=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    turn_type: Mapped[str] = mapped_column(String(16), nullable=False)
    question_content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    follow_up_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InterviewAnswerModel(Base):
    __tablename__ = "interview_answers"
    __table_args__ = (
        UniqueConstraint("session_id", "request_id", name="uq_interview_answers_session_request"),
        UniqueConstraint("turn_id", name="uq_interview_answers_turn"),
        Index("ix_interview_answers_session_created_at", "session_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    turn_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("interview_turns.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class InterviewEvaluationModel(Base):
    __tablename__ = "interview_evaluations"
    __table_args__ = (
        UniqueConstraint("turn_id", name="uq_interview_evaluations_turn"),
        CheckConstraint(
            "overall_score BETWEEN 0 AND 100", name="ck_interview_evaluations_overall_score"
        ),
        CheckConstraint(
            "technical_score BETWEEN 0 AND 100", name="ck_interview_evaluations_technical_score"
        ),
        CheckConstraint(
            "relevance_score BETWEEN 0 AND 100", name="ck_interview_evaluations_relevance_score"
        ),
        CheckConstraint(
            "clarity_score BETWEEN 0 AND 100", name="ck_interview_evaluations_clarity_score"
        ),
        CheckConstraint(
            "depth_score BETWEEN 0 AND 100", name="ck_interview_evaluations_depth_score"
        ),
        Index("ix_interview_evaluations_turn_created_at", "turn_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    turn_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("interview_turns.id", ondelete="CASCADE"), nullable=False
    )
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)
    technical_score: Mapped[int] = mapped_column(Integer, nullable=False)
    relevance_score: Mapped[int] = mapped_column(Integer, nullable=False)
    clarity_score: Mapped[int] = mapped_column(Integer, nullable=False)
    depth_score: Mapped[int] = mapped_column(Integer, nullable=False)
    strengths: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    weaknesses: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    feedback: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_improvements: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    llm_should_follow_up: Mapped[bool] = mapped_column(Boolean, nullable=False)
    follow_up_focus: Mapped[str | None] = mapped_column(String(500), nullable=True)
    follow_up_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
