from datetime import datetime
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.interview.domain import (
    InterviewDifficulty,
    InterviewQuestion,
    InterviewQuestionCitation,
    InterviewSession,
    InterviewStatus,
    InterviewType,
)


class CreateInterviewSessionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    knowledge_base_id: UUID = Field(alias="knowledgeBaseId")
    job_title: str = Field(alias="jobTitle", min_length=1, max_length=200)
    job_description: str = Field(alias="jobDescription", min_length=1, max_length=20000)
    interview_type: InterviewType = Field(default=InterviewType.TECHNICAL, alias="interviewType")
    difficulty: InterviewDifficulty = InterviewDifficulty.MEDIUM
    question_count: int = Field(default=8, alias="questionCount", ge=3, le=20)
    request_id: str | None = Field(default=None, alias="requestId", max_length=128)


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
    started_at: datetime | None = Field(default=None, alias="startedAt")
    finished_at: datetime | None = Field(default=None, alias="finishedAt")

    @classmethod
    def from_domain(cls, session: InterviewSession) -> "InterviewSessionResponse":
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
            startedAt=session.started_at,
            finishedAt=session.finished_at,
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
