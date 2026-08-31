from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class InterviewStatus(StrEnum):
    CREATED = "CREATED"
    PREPARING = "PREPARING"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ResumeEvaluationStatus(StrEnum):
    PENDING = "PENDING"
    EVALUATING = "EVALUATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


class InterviewDifficulty(StrEnum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


class InterviewType(StrEnum):
    TECHNICAL = "TECHNICAL"
    BEHAVIORAL = "BEHAVIORAL"
    MIXED = "MIXED"


class TurnType(StrEnum):
    PRIMARY = "PRIMARY"
    FOLLOW_UP = "FOLLOW_UP"


class TurnStatus(StrEnum):
    WAITING_ANSWER = "WAITING_ANSWER"
    EVALUATING = "EVALUATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class InterviewSession:
    id: UUID
    user_id: UUID
    knowledge_base_id: UUID
    job_title: str
    job_description: str
    interview_type: InterviewType
    difficulty: InterviewDifficulty
    question_count: int
    status: InterviewStatus
    current_question_index: int
    version: int
    request_id: str | None
    failure_code: str | None
    failure_message: str | None
    created_at: datetime
    updated_at: datetime
    prepared_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    preparation_queued_at: datetime | None = None
    preparation_started_at: datetime | None = None
    preparation_attempt_count: int = 0

    @classmethod
    def new(
        cls,
        *,
        user_id: UUID,
        knowledge_base_id: UUID,
        job_title: str,
        job_description: str,
        interview_type: InterviewType,
        difficulty: InterviewDifficulty,
        question_count: int,
        request_id: str | None,
    ) -> "InterviewSession":
        now = utc_now()
        return cls(
            id=uuid4(),
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            job_title=job_title,
            job_description=job_description,
            interview_type=interview_type,
            difficulty=difficulty,
            question_count=question_count,
            status=InterviewStatus.CREATED,
            current_question_index=0,
            version=0,
            request_id=request_id,
            failure_code=None,
            failure_message=None,
            created_at=now,
            updated_at=now,
            prepared_at=None,
            started_at=None,
            finished_at=None,
            preparation_queued_at=None,
            preparation_started_at=None,
            preparation_attempt_count=0,
        )


@dataclass(slots=True)
class ResumeEvaluation:
    id: UUID
    session_id: UUID
    user_id: UUID
    knowledge_base_id: UUID
    status: ResumeEvaluationStatus
    overall_score: int | None
    skills_match_score: int | None
    experience_match_score: int | None
    evidence_quality_score: int | None
    clarity_score: int | None
    strengths: list[str]
    gaps: list[str]
    suggestions: list[str]
    summary: str | None
    source_document_ids: list[UUID]
    evaluation_version: str
    provider_name: str | None
    failure_code: str | None
    failure_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class InterviewDemeanorEvaluation:
    id: UUID
    session_id: UUID
    user_id: UUID
    overall_score: int
    eye_contact_score: int
    posture_score: int
    facial_visibility_score: int
    expression_naturalness_score: int
    summary: str
    suggestions: list[str]
    confidence: int
    provider_name: str
    analysis_version: str
    captured_at: datetime
    created_at: datetime


@dataclass(slots=True)
class InterviewQuestion:
    id: UUID
    session_id: UUID
    sequence: int
    content: str
    category: str
    difficulty: InterviewDifficulty
    expected_points: list[str]
    source_summary: str | None
    created_at: datetime
    citations: list["InterviewQuestionCitation"] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class InterviewQuestionCitation:
    id: UUID
    question_id: UUID
    chunk_id: UUID
    document_id: UUID
    source_id: str
    page_number: int | None
    score: float
    excerpt: str
    ordinal: int
    created_at: datetime
    document_name: str | None = None


@dataclass(frozen=True, slots=True)
class InterviewEvent:
    id: UUID
    session_id: UUID
    event_type: str
    from_status: InterviewStatus | None
    to_status: InterviewStatus
    payload: dict[str, Any]
    idempotency_key: str | None
    created_at: datetime


@dataclass(slots=True)
class InterviewTurn:
    id: UUID
    session_id: UUID
    question_id: UUID | None
    parent_turn_id: UUID | None
    sequence: int
    turn_type: TurnType
    question_content: str
    status: TurnStatus
    follow_up_depth: int
    created_at: datetime
    answered_at: datetime | None
    evaluated_at: datetime | None
    evaluation_queued_at: datetime | None = None
    evaluation_started_at: datetime | None = None
    evaluation_completed_at: datetime | None = None
    evaluation_attempt_count: int = 0
    evaluation_failure_code: str | None = None
    evaluation_failure_message: str | None = None


@dataclass(frozen=True, slots=True)
class InterviewAnswer:
    id: UUID
    turn_id: UUID
    session_id: UUID
    user_id: UUID
    content: str
    request_id: str
    created_at: datetime


@dataclass(slots=True)
class InterviewEvaluation:
    id: UUID
    turn_id: UUID
    overall_score: int
    technical_score: int
    relevance_score: int
    clarity_score: int
    depth_score: int
    strengths: list[str]
    weaknesses: list[str]
    feedback: str
    suggested_improvements: list[str]
    llm_should_follow_up: bool
    follow_up_focus: str | None
    follow_up_question: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class InterviewProgress:
    session: InterviewSession
    turn: InterviewTurn
    answer: InterviewAnswer | None = None
    evaluation: InterviewEvaluation | None = None


@dataclass(frozen=True, slots=True)
class FollowUpDecision:
    should_follow_up: bool
    reason: str
