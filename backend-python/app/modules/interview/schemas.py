from datetime import datetime
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.interview.domain import (
    InterviewDemeanorEvaluation,
    InterviewDifficulty,
    InterviewEvaluation,
    InterviewProgress,
    InterviewQuestion,
    InterviewQuestionCitation,
    InterviewSession,
    InterviewStatus,
    InterviewType,
    ResumeEvaluation,
)


class CreateInterviewSessionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    knowledge_base_id: UUID = Field(alias="knowledgeBaseId")
    job_title: str = Field(alias="jobTitle", min_length=1, max_length=200)
    job_description: str = Field(alias="jobDescription", min_length=1, max_length=20000)
    interview_type: InterviewType = Field(default=InterviewType.TECHNICAL, alias="interviewType")
    difficulty: InterviewDifficulty = InterviewDifficulty.MEDIUM
    question_count: int = Field(default=5, alias="questionCount", ge=3, le=20)
    request_id: str | None = Field(default=None, alias="requestId", max_length=128)


class ResolveInterviewRoleRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    knowledge_base_id: UUID = Field(alias="knowledgeBaseId")


class ResolveInterviewRoleResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    job_title: str = Field(alias="jobTitle", min_length=1, max_length=200)
    job_description: str = Field(alias="jobDescription", min_length=1, max_length=20000)
    confidence: int | None = Field(default=None, ge=0, le=100)
    inferred: bool
    inference_version: str = Field(alias="inferenceVersion")


class DemeanorAnalysisCapabilitiesResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    available: bool
    provider: str
    max_image_bytes: int = Field(alias="maxImageBytes")
    max_pixels: int = Field(alias="maxPixels")
    min_interval_seconds: float = Field(alias="minIntervalSeconds")
    analysis_version: str = Field(alias="analysisVersion")


class DemeanorDimensionsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    eye_contact: int = Field(alias="eyeContact", ge=0, le=100)
    posture: int = Field(ge=0, le=100)
    facial_visibility: int = Field(alias="facialVisibility", ge=0, le=100)
    expression_naturalness: int = Field(alias="expressionNaturalness", ge=0, le=100)


class DemeanorEvaluationResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    session_id: UUID = Field(alias="sessionId")
    status: str
    overall_score: int = Field(alias="overallScore", ge=0, le=100)
    dimensions: DemeanorDimensionsResponse
    summary: str
    suggestions: list[str]
    confidence: int = Field(ge=0, le=100)
    captured_at: datetime = Field(alias="capturedAt")

    @classmethod
    def from_domain(cls, evaluation: InterviewDemeanorEvaluation) -> "DemeanorEvaluationResponse":
        return cls(
            id=evaluation.id,
            sessionId=evaluation.session_id,
            status="COMPLETED",
            overallScore=evaluation.overall_score,
            dimensions=DemeanorDimensionsResponse(
                eyeContact=evaluation.eye_contact_score,
                posture=evaluation.posture_score,
                facialVisibility=evaluation.facial_visibility_score,
                expressionNaturalness=evaluation.expression_naturalness_score,
            ),
            summary=evaluation.summary,
            suggestions=list(evaluation.suggestions),
            confidence=evaluation.confidence,
            capturedAt=evaluation.captured_at,
        )


class InterviewSessionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    session_id: str = Field(alias="sessionId")
    user_id: UUID = Field(alias="userId")
    knowledge_base_id: UUID = Field(alias="knowledgeBaseId")
    job_title: str = Field(alias="jobTitle")
    interview_type: str = Field(alias="interviewType")
    difficulty: str
    question_count: int = Field(alias="questionCount")
    status: str
    current_question_index: int = Field(alias="currentQuestionIndex")
    preparation_progress: int = Field(alias="preparationProgress")
    can_start: bool = Field(alias="canStart")
    version: int
    request_id: str | None = Field(default=None, alias="requestId")
    failure_code: str | None = Field(default=None, alias="failureCode")
    failure_message: str | None = Field(default=None, alias="failureMessage")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    prepared_at: datetime | None = Field(default=None, alias="preparedAt")
    preparation_queued_at: datetime | None = Field(
        default=None, alias="preparationQueuedAt"
    )
    preparation_started_at: datetime | None = Field(
        default=None, alias="preparationStartedAt"
    )
    preparation_attempt_count: int = Field(default=0, alias="preparationAttemptCount")
    started_at: datetime | None = Field(default=None, alias="startedAt")
    finished_at: datetime | None = Field(default=None, alias="finishedAt")
    resume_score: int | None = Field(default=None, alias="resumeScore")
    resume_evaluation_status: str | None = Field(default=None, alias="resumeEvaluationStatus")
    resume_evaluation: "ResumeEvaluationResponse | None" = Field(
        default=None, alias="resumeEvaluation"
    )

    @classmethod
    def from_domain(
        cls,
        session: InterviewSession,
        resume_evaluation: ResumeEvaluation | None = None,
    ) -> "InterviewSessionResponse":
        progress = {
            InterviewStatus.CREATED: 0,
            InterviewStatus.PREPARING: 50,
            InterviewStatus.READY: 100,
            InterviewStatus.IN_PROGRESS: 100,
            InterviewStatus.COMPLETED: 100,
            InterviewStatus.FAILED: 100,
            InterviewStatus.CANCELLED: 100,
        }[session.status]
        return cls(
            id=session.id,
            sessionId=str(session.id),
            userId=session.user_id,
            knowledgeBaseId=session.knowledge_base_id,
            jobTitle=session.job_title,
            interviewType=session.interview_type.value,
            difficulty=session.difficulty.value,
            questionCount=session.question_count,
            status=session.status.value,
            currentQuestionIndex=session.current_question_index,
            preparationProgress=progress,
            canStart=session.status == InterviewStatus.READY,
            version=session.version,
            requestId=session.request_id,
            failureCode=session.failure_code,
            failureMessage=session.failure_message,
            createdAt=session.created_at,
            updatedAt=session.updated_at,
            preparedAt=session.prepared_at,
            preparationQueuedAt=session.preparation_queued_at,
            preparationStartedAt=session.preparation_started_at,
            preparationAttemptCount=session.preparation_attempt_count,
            startedAt=session.started_at,
            finishedAt=session.finished_at,
            resumeScore=(resume_evaluation.overall_score if resume_evaluation else None),
            resumeEvaluationStatus=(
                resume_evaluation.status.value if resume_evaluation else None
            ),
            resumeEvaluation=(
                ResumeEvaluationResponse.from_domain(resume_evaluation)
                if resume_evaluation
                else None
            ),
        )


class ResumeEvaluationResponse(BaseModel):
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
    evaluated_at: datetime | None = Field(default=None, alias="evaluatedAt")
    failure_code: str | None = Field(default=None, alias="failureCode")

    @classmethod
    def from_domain(cls, evaluation: ResumeEvaluation) -> "ResumeEvaluationResponse":
        return cls(
            status=evaluation.status.value,
            overallScore=evaluation.overall_score,
            skillsMatchScore=evaluation.skills_match_score,
            experienceMatchScore=evaluation.experience_match_score,
            evidenceQualityScore=evaluation.evidence_quality_score,
            clarityScore=evaluation.clarity_score,
            strengths=list(evaluation.strengths),
            gaps=list(evaluation.gaps),
            suggestions=list(evaluation.suggestions),
            summary=evaluation.summary,
            evaluationVersion=evaluation.evaluation_version,
            evaluatedAt=evaluation.completed_at,
            failureCode=evaluation.failure_code,
        )


InterviewSessionResponse.model_rebuild()


class InterviewConversationResponse(BaseModel):
    """Legacy conversation summary used by the original interview intro page."""

    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(alias="sessionId")
    conversation_title: str | None = Field(default=None, alias="conversationTitle")
    status: str | None = None
    interview_type: str | None = Field(default=None, alias="interviewType")
    resume_file_url: str | None = Field(default=None, alias="resumeFileUrl")
    create_time: datetime | None = Field(default=None, alias="createTime")
    update_time: datetime | None = Field(default=None, alias="updateTime")

    @classmethod
    def from_domain(cls, session: InterviewSession) -> "InterviewConversationResponse":
        status = {
            InterviewStatus.CREATED: "DRAFT",
            InterviewStatus.PREPARING: "RESUME_UPLOADING",
            InterviewStatus.READY: "READY",
            InterviewStatus.IN_PROGRESS: "IN_PROGRESS",
            InterviewStatus.COMPLETED: "COMPLETED",
            InterviewStatus.FAILED: "FAILED",
            InterviewStatus.CANCELLED: "CANCELLED",
        }[session.status]
        return cls(
            sessionId=str(session.id),
            conversationTitle=session.job_title or None,
            status=status,
            interviewType=session.interview_type.value,
            resumeFileUrl=None,
            createTime=session.created_at,
            updateTime=session.updated_at,
        )


class InterviewQuestionCitationResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    question_id: UUID = Field(alias="questionId")
    chunk_id: UUID = Field(alias="chunkId")
    document_id: UUID = Field(alias="documentId")
    source_id: str = Field(alias="sourceId")
    page_number: int | None = Field(default=None, alias="pageNumber")
    score: float
    excerpt: str
    ordinal: int
    created_at: datetime = Field(alias="createdAt")

    @classmethod
    def from_domain(
        cls, citation: InterviewQuestionCitation
    ) -> "InterviewQuestionCitationResponse":
        return cls(
            id=citation.id,
            questionId=citation.question_id,
            chunkId=citation.chunk_id,
            documentId=citation.document_id,
            sourceId=citation.source_id,
            pageNumber=citation.page_number,
            score=citation.score,
            excerpt=citation.excerpt,
            ordinal=citation.ordinal,
            createdAt=citation.created_at,
        )


class InterviewQuestionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    session_id: UUID = Field(alias="sessionId")
    sequence: int
    content: str
    category: str
    difficulty: str
    expected_points: list[str] = Field(alias="expectedPoints")
    source_summary: str | None = Field(default=None, alias="sourceSummary")
    created_at: datetime = Field(alias="createdAt")
    citations: list[InterviewQuestionCitationResponse] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, question: InterviewQuestion) -> "InterviewQuestionResponse":
        return cls(
            id=question.id,
            sessionId=question.session_id,
            sequence=question.sequence,
            content=question.content,
            category=question.category,
            difficulty=question.difficulty.value,
            expectedPoints=list(question.expected_points),
            sourceSummary=question.source_summary,
            createdAt=question.created_at,
            citations=[
                InterviewQuestionCitationResponse.from_domain(citation)
                for citation in question.citations
            ],
        )


T = TypeVar("T")


class InterviewPageResponse[T](BaseModel):
    records: list[T]
    total: int
    size: int
    current: int
    pages: int

    @classmethod
    def build(
        cls, records: list[T], total: int, current: int, size: int
    ) -> "InterviewPageResponse[T]":
        return cls(
            records=records,
            total=total,
            size=size,
            current=current,
            pages=(total + size - 1) // size if size else 0,
        )


class SubmitInterviewAnswerRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    turn_id: UUID = Field(alias="turnId")
    answer: str = Field(min_length=1)
    request_id: str = Field(alias="requestId", min_length=1, max_length=128)


class SubmitInterviewAnswerResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: UUID = Field(alias="sessionId")
    turn_id: UUID = Field(alias="turnId")
    status: str
    request_id: str = Field(alias="requestId")


class InterviewEvaluationResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    turn_id: UUID = Field(alias="turnId")
    overall_score: int = Field(alias="overallScore")
    technical_score: int = Field(alias="technicalScore")
    relevance_score: int = Field(alias="relevanceScore")
    clarity_score: int = Field(alias="clarityScore")
    depth_score: int = Field(alias="depthScore")
    strengths: list[str]
    weaknesses: list[str]
    feedback: str
    suggested_improvements: list[str] = Field(alias="suggestedImprovements")
    should_follow_up: bool = Field(alias="shouldFollowUp")
    follow_up_focus: str | None = Field(default=None, alias="followUpFocus")
    follow_up_question: str | None = Field(default=None, alias="followUpQuestion")
    created_at: datetime = Field(alias="createdAt")

    @classmethod
    def from_domain(cls, evaluation: InterviewEvaluation) -> "InterviewEvaluationResponse":
        return cls(
            id=evaluation.id,
            turnId=evaluation.turn_id,
            overallScore=evaluation.overall_score,
            technicalScore=evaluation.technical_score,
            relevanceScore=evaluation.relevance_score,
            clarityScore=evaluation.clarity_score,
            depthScore=evaluation.depth_score,
            strengths=list(evaluation.strengths),
            weaknesses=list(evaluation.weaknesses),
            feedback=evaluation.feedback,
            suggestedImprovements=list(evaluation.suggested_improvements),
            shouldFollowUp=evaluation.llm_should_follow_up,
            followUpFocus=evaluation.follow_up_focus,
            followUpQuestion=evaluation.follow_up_question,
            createdAt=evaluation.created_at,
        )


class InterviewTurnResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    turn_id: UUID = Field(alias="turnId")
    session_id: UUID = Field(alias="sessionId")
    question_id: UUID | None = Field(default=None, alias="questionId")
    parent_turn_id: UUID | None = Field(default=None, alias="parentTurnId")
    turn_type: str = Field(alias="turnType")
    question: str
    sequence: int
    follow_up_depth: int = Field(alias="followUpDepth")
    status: str
    can_answer: bool = Field(alias="canAnswer")
    answer: str | None = None
    answer_request_id: str | None = Field(default=None, alias="answerRequestId")
    answered_at: datetime | None = Field(default=None, alias="answeredAt")
    evaluation: InterviewEvaluationResponse | None = None
    created_at: datetime = Field(alias="createdAt")
    evaluated_at: datetime | None = Field(default=None, alias="evaluatedAt")

    @classmethod
    def from_progress(cls, progress: InterviewProgress) -> "InterviewTurnResponse":
        answer = progress.answer
        evaluation = progress.evaluation
        return cls(
            turnId=progress.turn.id,
            sessionId=progress.turn.session_id,
            questionId=progress.turn.question_id,
            parentTurnId=progress.turn.parent_turn_id,
            turnType=progress.turn.turn_type.value,
            question=progress.turn.question_content,
            sequence=progress.turn.sequence,
            followUpDepth=progress.turn.follow_up_depth,
            status=progress.turn.status.value,
            canAnswer=progress.turn.status.value == "WAITING_ANSWER",
            answer=answer.content if answer else None,
            answerRequestId=answer.request_id if answer else None,
            answeredAt=progress.turn.answered_at,
            evaluation=InterviewEvaluationResponse.from_domain(evaluation)
            if evaluation
            else None,
            createdAt=progress.turn.created_at,
            evaluatedAt=progress.turn.evaluated_at,
        )
