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


class ResumeEvaluationSnapshotResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    overall_score: int | None = Field(default=None, alias="overallScore")
    skills_match_score: int | None = Field(default=None, alias="skillsMatchScore")
    experience_match_score: int | None = Field(default=None, alias="experienceMatchScore")
    evidence_quality_score: int | None = Field(default=None, alias="evidenceQualityScore")
    clarity_score: int | None = Field(default=None, alias="clarityScore")
    strengths: list[str]
    gaps: list[str]
    suggestions: list[str]
    summary: str | None = None
    evaluation_version: str = Field(alias="evaluationVersion")
    provider_name: str | None = Field(default=None, alias="providerName")
    evaluated_at: datetime | None = Field(default=None, alias="evaluatedAt")
    failure_code: str | None = Field(default=None, alias="failureCode")


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
    resume_score: int | None = Field(default=None, alias="resumeScore")
    resume_evaluation: ResumeEvaluationSnapshotResponse | None = Field(
        default=None, alias="resumeEvaluation"
    )

    @classmethod
    def from_detail(cls, detail: InterviewReportDetail) -> "InterviewReportResponse":
        report = detail.report
        resume_snapshot = _resume_snapshot_response(report.resume_evaluation_snapshot)
        resume_score = resume_snapshot.overall_score if resume_snapshot else None
        dimension_scores = {
            "technical": report.technical_score,
            "relevance": report.relevance_score,
            "clarity": report.clarity_score,
            "depth": report.depth_score,
        }
        radar_data = list(report.radar_data)
        if resume_score is not None:
            dimension_scores["resume"] = resume_score
            resume_radar_point = {"dimension": "resume", "score": resume_score}
            replaced_resume_point = False
            normalized_radar_data: list[dict[str, object]] = []
            for point in radar_data:
                if point.get("dimension") == "resume":
                    if not replaced_resume_point:
                        normalized_radar_data.append(resume_radar_point)
                        replaced_resume_point = True
                    continue
                normalized_radar_data.append(point)
            if not replaced_resume_point:
                normalized_radar_data.insert(0, resume_radar_point)
            radar_data = normalized_radar_data
        demeanor_score = next(
            (
                point.get("score")
                for point in radar_data
                if point.get("dimension") == "demeanor"
                and isinstance(point.get("score"), int)
            ),
            None,
        )
        if isinstance(demeanor_score, int):
            dimension_scores["demeanor"] = max(0, min(100, demeanor_score))
        return cls(
            reportId=report.id,
            sessionId=report.session_id,
            status=report.status.value,
            jobTitle=detail.session.job_title,
            interviewType=detail.session.interview_type.value,
            difficulty=detail.session.difficulty.value,
            overallScore=report.overall_score,
            dimensionScores=dimension_scores,
            radarData=radar_data,
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
            resumeScore=resume_score,
            resumeEvaluation=resume_snapshot,
        )


def _resume_snapshot_response(
    snapshot: dict[str, object] | None,
) -> ResumeEvaluationSnapshotResponse | None:
    if not snapshot:
        return None
    return ResumeEvaluationSnapshotResponse(
        status=str(snapshot.get("status", "FAILED")),
        overallScore=_optional_int(snapshot.get("overallScore")),
        skillsMatchScore=_optional_int(snapshot.get("skillsMatchScore")),
        experienceMatchScore=_optional_int(snapshot.get("experienceMatchScore")),
        evidenceQualityScore=_optional_int(snapshot.get("evidenceQualityScore")),
        clarityScore=_optional_int(snapshot.get("clarityScore")),
        strengths=_string_list(snapshot.get("strengths")),
        gaps=_string_list(snapshot.get("gaps")),
        suggestions=_string_list(snapshot.get("suggestions")),
        summary=(str(snapshot["summary"]) if snapshot.get("summary") is not None else None),
        evaluationVersion=str(snapshot.get("evaluationVersion", "unknown")),
        providerName=(
            str(snapshot["providerName"])
            if snapshot.get("providerName") is not None
            else None
        ),
        evaluatedAt=_parse_datetime(snapshot.get("evaluatedAt")),
        failureCode=(
            str(snapshot["failureCode"])
            if snapshot.get("failureCode") is not None
            else None
        ),
    )


def _optional_int(value: object) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    return max(0, min(100, value))


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)][:10]


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


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
