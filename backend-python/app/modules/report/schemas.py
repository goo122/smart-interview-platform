from datetime import datetime
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.report.domain import InterviewReportDetail, InterviewReportItem


class InterviewReportItemResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    turn_id: UUID = Field(alias="turnId")
    parent_turn_id: UUID | None = Field(default=None, alias="parentTurnId")
    sequence: int
    turn_type: str = Field(alias="turnType")
    question: str
    answer: str
    scores: dict[str, int]
    strengths: list[str]
    weaknesses: list[str]
    feedback: str
    suggested_improvements: list[str] = Field(alias="suggestedImprovements")
    sources: list[dict[str, object]]
    created_at: datetime = Field(alias="createdAt")

    @classmethod
    def from_domain(cls, item: InterviewReportItem) -> "InterviewReportItemResponse":
        return cls(
            id=item.id,
            turnId=item.turn_id,
            parentTurnId=item.parent_turn_id,
            sequence=item.sequence,
            turnType=item.turn_type,
            question=item.question,
            answer=item.answer,
            scores={
                "overall": item.overall_score,
                "technical": item.technical_score,
                "relevance": item.relevance_score,
                "clarity": item.clarity_score,
                "depth": item.depth_score,
            },
            strengths=list(item.strengths),
            weaknesses=list(item.weaknesses),
            feedback=item.feedback,
            suggestedImprovements=list(item.suggested_improvements),
            sources=list(item.sources),
            createdAt=item.created_at,
        )


class InterviewReportResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    report_id: UUID = Field(alias="reportId")
    session_id: UUID = Field(alias="sessionId")
    status: str
    job_title: str = Field(alias="jobTitle")
    interview_type: str = Field(alias="interviewType")
    difficulty: str
    overall_score: int = Field(alias="overallScore")
    dimension_scores: dict[str, int] = Field(alias="dimensionScores")
    radar_data: list[dict[str, object]] = Field(alias="radarData")
    summary: str
    strengths: list[str]
    weaknesses: list[str]
    suggested_improvements: list[str] = Field(alias="suggestedImprovements")
    action_plan: list[str] = Field(alias="actionPlan")
    recommended_level: str | None = Field(default=None, alias="recommendedLevel")
    items: list[InterviewReportItemResponse]
    aggregation_version: str = Field(alias="aggregationVersion")
    generated_by: str = Field(alias="generatedBy")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    completed_at: datetime | None = Field(default=None, alias="completedAt")
    failure_code: str | None = Field(default=None, alias="failureCode")
    failure_message: str | None = Field(default=None, alias="failureMessage")

    @classmethod
    def from_detail(cls, detail: InterviewReportDetail) -> "InterviewReportResponse":
        report = detail.report
        return cls(
            reportId=report.id,
            sessionId=report.session_id,
            status=report.status.value,
            jobTitle=detail.session.job_title,
            interviewType=detail.session.interview_type.value,
            difficulty=detail.session.difficulty.value,
            overallScore=report.overall_score,
            dimensionScores={
                "technical": report.technical_score,
                "relevance": report.relevance_score,
                "clarity": report.clarity_score,
                "depth": report.depth_score,
            },
            radarData=list(report.radar_data),
            summary=report.summary,
            strengths=list(report.strengths),
            weaknesses=list(report.weaknesses),
            suggestedImprovements=list(report.suggested_improvements),
            actionPlan=list(report.action_plan),
            recommendedLevel=report.recommended_level,
            items=[InterviewReportItemResponse.from_domain(item) for item in detail.items],
            aggregationVersion=report.aggregation_version,
            generatedBy=report.generated_by.value,
            createdAt=report.created_at,
            updatedAt=report.updated_at,
            completedAt=report.completed_at,
            failureCode=report.failure_code,
            failureMessage=report.failure_message,
        )


T = TypeVar("T")


class InterviewReportPageResponse[T](BaseModel):
    records: list[T]
    total: int
    size: int
    current: int
    pages: int

    @classmethod
    def build(
        cls, records: list[T], total: int, current: int, size: int
    ) -> "InterviewReportPageResponse[T]":
        return cls(
            records=records,
            total=total,
            size=size,
            current=current,
            pages=(total + size - 1) // size if size else 0,
        )
