from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from app.modules.interview.domain import (
    InterviewEvaluation,
    InterviewQuestion,
    InterviewSession,
    InterviewTurn,
)


class ReportStatus(StrEnum):
    PENDING = "PENDING"
    GENERATING = "GENERATING"
    READY = "READY"
    FAILED = "FAILED"


class ReportGeneratedBy(StrEnum):
    RULES = "RULES"
    LLM = "LLM"
    HYBRID = "HYBRID"


@dataclass(slots=True)
class InterviewReport:
    id: UUID
    session_id: UUID
    user_id: UUID
    status: ReportStatus
    overall_score: int
    technical_score: int
    relevance_score: int
    clarity_score: int
    depth_score: int
    radar_data: list[dict[str, Any]]
    strengths: list[str]
    weaknesses: list[str]
    suggested_improvements: list[str]
    summary: str
    action_plan: list[str]
    recommended_level: str | None
    aggregation_version: str
    prompt_version: str | None
    generated_by: ReportGeneratedBy
    failure_code: str | None
    failure_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class InterviewReportItem:
    id: UUID
    report_id: UUID
    turn_id: UUID
    parent_turn_id: UUID | None
    sequence: int
    turn_type: str
    question: str
    answer: str
    overall_score: int
    technical_score: int
    relevance_score: int
    clarity_score: int
    depth_score: int
    strengths: list[str]
    weaknesses: list[str]
    feedback: str
    suggested_improvements: list[str]
    sources: list[dict[str, Any]]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class InterviewReportDetail:
    report: InterviewReport
    session: InterviewSession
    items: tuple[InterviewReportItem, ...]


@dataclass(frozen=True, slots=True)
class ReportTurnSnapshot:
    turn: InterviewTurn
    answer: str
    evaluation: InterviewEvaluation
    question: InterviewQuestion | None
