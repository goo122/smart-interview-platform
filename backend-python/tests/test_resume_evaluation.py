from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from test_interview import FakeInterviewContextProvider, InMemoryInterviewRepository

from app.ai.interview import FakeInterviewQuestionGenerator
from app.ai.resume import (
    FakeResumeEvaluator,
    ResumeEvaluationRequest,
    StructuredResumeEvaluation,
    UnavailableResumeEvaluator,
)
from app.modules.interview.context import InterviewContext
from app.modules.interview.domain import (
    InterviewDifficulty,
    InterviewSession,
    InterviewStatus,
    InterviewType,
    ResumeEvaluation,
    ResumeEvaluationStatus,
)
from app.modules.interview.schemas import InterviewSessionResponse
from app.modules.interview.workflow import (
    InterviewPreparationWorkflow,
    InterviewResumeEvaluationWorkflow,
)
from app.modules.report.domain import (
    InterviewReport,
    InterviewReportDetail,
    ReportGeneratedBy,
    ReportStatus,
)
from app.modules.report.schemas import InterviewReportResponse
from app.workers.queue import InterviewResumeEvaluationJob


def _session() -> InterviewSession:
    return InterviewSession.new(
        user_id=uuid4(),
        knowledge_base_id=uuid4(),
        job_title="Python 工程师",
        job_description="负责后端服务和系统设计",
        interview_type=InterviewType.TECHNICAL,
        difficulty=InterviewDifficulty.MEDIUM,
        question_count=3,
        request_id="resume-test",
    )


def test_structured_resume_evaluation_is_bounded_and_normalized() -> None:
    result = StructuredResumeEvaluation(
        overall_score=130,
        skills_match_score=-3,
        experience_match_score=75.4,
        evidence_quality_score="88",
        clarity_score=0,
        strengths="有项目经验",
        gaps=[],
        suggestions=["补充指标"],
        summary="  匹配良好  ",
    )
    assert result.overall_score == 100
    assert result.skills_match_score == 0
    assert result.experience_match_score == 75
    assert result.strengths == ["有项目经验"]
    assert result.gaps
    assert result.summary == "匹配良好"


@pytest.mark.asyncio
async def test_fake_resume_evaluator_is_stable_and_receives_job_context() -> None:
    evaluator = FakeResumeEvaluator()
    request = ResumeEvaluationRequest(
        job_title="Java 工程师",
        job_description="负责微服务",
        resume_context="不可信简历内容",
        source_ids=("[S1]",),
    )
    first = await evaluator.evaluate(request)
    second = await evaluator.evaluate(request)
    assert first == second
    assert first.overall_score == 86
    assert evaluator.calls == 2
    assert evaluator.requests[0].source_ids == ("[S1]",)


@pytest.mark.asyncio
async def test_unavailable_resume_evaluator_does_not_fabricate_score() -> None:
    with pytest.raises(RuntimeError, match="configured"):
        await UnavailableResumeEvaluator().evaluate(
            ResumeEvaluationRequest("岗位", "描述", "简历", ("[S1]",))
        )


def test_session_response_exposes_resume_score_without_password_or_source_text() -> None:
    session = _session()
    evaluation = ResumeEvaluation(
        id=uuid4(),
        session_id=session.id,
        user_id=session.user_id,
        knowledge_base_id=session.knowledge_base_id,
        status=ResumeEvaluationStatus.COMPLETED,
        overall_score=86,
        skills_match_score=88,
        experience_match_score=84,
        evidence_quality_score=82,
        clarity_score=90,
        strengths=["项目相关"],
        gaps=["缺少指标"],
        suggestions=["补充结果"],
        summary="匹配度良好",
        source_document_ids=[uuid4()],
        evaluation_version="resume-match-v1",
        provider_name="FakeResumeEvaluator",
        failure_code=None,
        failure_message=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    payload = InterviewSessionResponse.from_domain(session, evaluation).model_dump(
        by_alias=True
    )
    assert payload["resumeScore"] == 86
    assert payload["resumeEvaluation"]["suggestions"] == ["补充结果"]
    assert "password_hash" not in str(payload)
    assert "不可信" not in str(payload)


def test_report_response_uses_persisted_resume_snapshot() -> None:
    session = _session()
    now = datetime.now(UTC)
    report = InterviewReport(
        id=uuid4(),
        session_id=session.id,
        user_id=session.user_id,
        status=ReportStatus.READY,
        overall_score=80,
        technical_score=80,
        relevance_score=80,
        clarity_score=80,
        depth_score=80,
        radar_data=[{"dimension": "technical", "score": 80}],
        strengths=["回答清晰"],
        weaknesses=["补充指标"],
        suggested_improvements=["继续练习"],
        summary="面试完成",
        action_plan=["复盘"],
        recommended_level="中级",
        aggregation_version="v1",
        prompt_version=None,
        generated_by=ReportGeneratedBy.HYBRID,
        failure_code=None,
        failure_message=None,
        created_at=now,
        updated_at=now,
        completed_at=now,
        resume_evaluation_snapshot={
            "status": "COMPLETED",
            "overallScore": 86,
            "skillsMatchScore": 88,
            "experienceMatchScore": 84,
            "evidenceQualityScore": 82,
            "clarityScore": 90,
            "strengths": ["项目相关"],
            "gaps": ["缺少指标"],
            "suggestions": ["补充结果"],
            "summary": "匹配度良好",
            "evaluationVersion": "resume-match-v1",
            "providerName": "FakeResumeEvaluator",
            "evaluatedAt": now.isoformat(),
        },
    )
    response = InterviewReportResponse.from_detail(
        InterviewReportDetail(report=report, session=session, items=())
    )
    assert response.resume_score == 86
    assert response.dimension_scores["resume"] == 86
    assert response.radar_data[0] == {"dimension": "resume", "score": 86}
    assert response.resume_evaluation is not None
    assert response.resume_evaluation.gaps == ["缺少指标"]


class _ResumeRepository(InMemoryInterviewRepository):
    def __init__(self) -> None:
        super().__init__()
        self.resume_evaluations: dict[UUID, ResumeEvaluation] = {}

    async def get_resume_evaluation(self, session_id: UUID, user_id: UUID):
        value = self.resume_evaluations.get(session_id)
        return value if value and value.user_id == user_id else None

    async def create_resume_evaluation_pending(
        self, session_id: UUID, user_id: UUID, knowledge_base_id: UUID, version: str
    ) -> ResumeEvaluation:
        existing = await self.get_resume_evaluation(session_id, user_id)
        if existing:
            return existing
        now = datetime.now(UTC)
        value = ResumeEvaluation(
            id=uuid4(), session_id=session_id, user_id=user_id,
            knowledge_base_id=knowledge_base_id, status=ResumeEvaluationStatus.PENDING,
            overall_score=None, skills_match_score=None, experience_match_score=None,
            evidence_quality_score=None, clarity_score=None, strengths=[], gaps=[],
            suggestions=[], summary=None, source_document_ids=[],
            evaluation_version=version, provider_name=None, failure_code=None,
            failure_message=None, created_at=now, updated_at=now, completed_at=None,
        )
        self.resume_evaluations[session_id] = value
        return value

    async def claim_resume_evaluation(self, session_id: UUID, user_id: UUID):
        value = self.resume_evaluations[session_id]
        if value.status in {ResumeEvaluationStatus.COMPLETED, ResumeEvaluationStatus.UNAVAILABLE}:
            return value, False
        value.status = ResumeEvaluationStatus.EVALUATING
        return value, True

    async def persist_resume_evaluation(self, session_id, user_id, evaluation, **kwargs):
        value = self.resume_evaluations[session_id]
        value.status = ResumeEvaluationStatus.COMPLETED
        value.overall_score = evaluation.overall_score
        value.skills_match_score = evaluation.skills_match_score
        value.experience_match_score = evaluation.experience_match_score
        value.evidence_quality_score = evaluation.evidence_quality_score
        value.clarity_score = evaluation.clarity_score
        value.strengths = list(evaluation.strengths)
        value.gaps = list(evaluation.gaps)
        value.suggestions = list(evaluation.suggestions)
        value.summary = evaluation.summary
        value.source_document_ids = list(kwargs["source_document_ids"])
        value.provider_name = kwargs["provider_name"]
        value.completed_at = datetime.now(UTC)
        return value

    async def mark_resume_evaluation_failed(
        self, session_id, user_id, status, failure_code, failure_message, **kwargs
    ):
        value = self.resume_evaluations[session_id]
        value.status = status
        value.failure_code = failure_code
        value.failure_message = failure_message
        value.completed_at = datetime.now(UTC)
        return value


class _DeferredResumeEvaluationQueue:
    def __init__(self) -> None:
        self.jobs: list[InterviewResumeEvaluationJob] = []

    async def enqueue_interview_resume_evaluation(
        self, job: InterviewResumeEvaluationJob
    ) -> None:
        self.jobs.append(job)


@pytest.mark.asyncio
async def test_slow_resume_evaluation_does_not_block_ready_preparation() -> None:
    repository = _ResumeRepository()
    session = _session()
    await repository.create(session)
    from app.modules.knowledge.context import ContextCitation

    evaluator = FakeResumeEvaluator(delay_seconds=0.05)
    queue = _DeferredResumeEvaluationQueue()
    workflow = InterviewPreparationWorkflow(
        repository,
        FakeInterviewContextProvider(
            context=InterviewContext(
                prompt="resume evidence",
                citations=(
                    ContextCitation(
                        source_id="[S1]", chunk_id=uuid4(), document_id=uuid4(),
                        document_name="resume.pdf", page_number=1, score=1.0,
                        excerpt="experience", ordinal=0,
                    ),
                ),
            ),
        ),
        FakeInterviewQuestionGenerator(),
        evaluator,
        queue,
    )
    result = await workflow.prepare(session.user_id, session.id)
    assert result.status == InterviewStatus.READY
    assert evaluator.calls == 0
    assert len(queue.jobs) == 1

    evaluation_workflow = InterviewResumeEvaluationWorkflow(
        repository,
        FakeInterviewContextProvider(
            context=InterviewContext(
                prompt="resume evidence",
                citations=(
                    ContextCitation(
                        source_id="[S1]", chunk_id=uuid4(), document_id=uuid4(),
                        document_name="resume.pdf", page_number=1, score=1.0,
                        excerpt="experience", ordinal=0,
                    ),
                ),
            ),
        ),
        evaluator,
    )
    evaluation = await evaluation_workflow.evaluate(session.user_id, session.id)
    assert evaluation is not None
    assert repository.resume_evaluations[session.id].status == ResumeEvaluationStatus.COMPLETED
    assert repository.resume_evaluations[session.id].overall_score == 86
    assert evaluator.calls == 1


@pytest.mark.asyncio
async def test_resume_evaluation_failure_does_not_fail_interview_preparation() -> None:
    repository = _ResumeRepository()
    session = _session()
    await repository.create(session)
    from app.modules.knowledge.context import ContextCitation

    evaluator = FakeResumeEvaluator(error=RuntimeError("provider unavailable"))
    queue = _DeferredResumeEvaluationQueue()
    workflow = InterviewPreparationWorkflow(
        repository,
        FakeInterviewContextProvider(
            context=InterviewContext(
                prompt="resume evidence",
                citations=(
                    ContextCitation(
                        source_id="[S1]", chunk_id=uuid4(), document_id=uuid4(),
                        document_name="resume.pdf", page_number=1, score=1.0,
                        excerpt="experience", ordinal=0,
                    ),
                ),
            )
        ),
        FakeInterviewQuestionGenerator(),
        evaluator,
        queue,
    )
    result = await workflow.prepare(session.user_id, session.id)
    assert result.status == InterviewStatus.READY
    assert repository.resume_evaluations[session.id].status == ResumeEvaluationStatus.PENDING

    evaluation_workflow = InterviewResumeEvaluationWorkflow(
        repository,
        FakeInterviewContextProvider(
            context=InterviewContext(
                prompt="resume evidence",
                citations=(
                    ContextCitation(
                        source_id="[S1]", chunk_id=uuid4(), document_id=uuid4(),
                        document_name="resume.pdf", page_number=1, score=1.0,
                        excerpt="experience", ordinal=0,
                    ),
                ),
            ),
        ),
        evaluator,
    )
    evaluation = await evaluation_workflow.evaluate(session.user_id, session.id)
    assert evaluation is not None
    assert repository.resume_evaluations[session.id].status == ResumeEvaluationStatus.FAILED
    assert repository.resume_evaluations[session.id].overall_score is None
