from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from test_interview import FakeTaskQueue, InMemoryInterviewRepository

from app.ai.report import FakeInterviewReportNarrativeGenerator
from app.core.config import Settings
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.domain import User
from app.modules.interview.domain import (
    InterviewAnswer,
    InterviewDifficulty,
    InterviewEvaluation,
    InterviewQuestion,
    InterviewQuestionCitation,
    InterviewSession,
    InterviewStatus,
    InterviewTurn,
    InterviewType,
    TurnStatus,
    TurnType,
)
from app.modules.interview.exceptions import InterviewNotFoundError
from app.modules.report.aggregation import InterviewScoreAggregator, ReportAggregationWeights
from app.modules.report.dependencies import get_interview_report_service
from app.modules.report.domain import (
    InterviewReport,
    InterviewReportItem,
    ReportGeneratedBy,
    ReportStatus,
)
from app.modules.report.exceptions import ReportSessionNotCompletedError
from app.modules.report.service import InterviewReportService


def _evaluation(turn_id: UUID, score: int, text: str = "strength") -> InterviewEvaluation:
    return InterviewEvaluation(
        id=uuid4(),
        turn_id=turn_id,
        overall_score=score,
        technical_score=score,
        relevance_score=score,
        clarity_score=score,
        depth_score=score,
        strengths=[text, text],
        weaknesses=["补充指标"],
        feedback="结构化反馈",
        suggested_improvements=["补充指标", "补充指标"],
        llm_should_follow_up=False,
        follow_up_focus=None,
        follow_up_question=None,
        created_at=datetime.now(UTC),
    )


def _completed_interview() -> tuple[InMemoryInterviewRepository, UUID, UUID]:
    repository = InMemoryInterviewRepository()
    user_id, base_id = uuid4(), uuid4()
    session = InterviewSession.new(
        user_id=user_id,
        knowledge_base_id=base_id,
        job_title="Python 工程师",
        job_description="负责后端系统开发",
        interview_type=InterviewType.TECHNICAL,
        difficulty=InterviewDifficulty.MEDIUM,
        question_count=3,
        request_id=None,
    )
    session.status = InterviewStatus.COMPLETED
    repository.sessions[session.id] = session
    repository.questions[session.id] = [
        InterviewQuestion(
            id=uuid4(),
            session_id=session.id,
            sequence=1,
            content="请说明项目方案",
            category="TECHNICAL",
            difficulty=InterviewDifficulty.MEDIUM,
            expected_points=["方案"],
            source_summary="项目来源",
            created_at=datetime.now(UTC),
            citations=[
                InterviewQuestionCitation(
                    id=uuid4(),
                    question_id=uuid4(),
                    chunk_id=uuid4(),
                    document_id=uuid4(),
                    source_id="[S1]",
                    page_number=2,
                    score=0.9,
                    excerpt="FastAPI 项目经验",
                    ordinal=0,
                    created_at=datetime.now(UTC),
                    document_name="resume.pdf",
                )
            ],
        )
    ]
    primary = InterviewTurn(
        id=uuid4(),
        session_id=session.id,
        question_id=repository.questions[session.id][0].id,
        parent_turn_id=None,
        sequence=1,
        turn_type=TurnType.PRIMARY,
        question_content="请说明项目方案",
        status=TurnStatus.COMPLETED,
        follow_up_depth=0,
        created_at=datetime.now(UTC),
        answered_at=datetime.now(UTC),
        evaluated_at=datetime.now(UTC),
    )
    follow_up = InterviewTurn(
        id=uuid4(),
        session_id=session.id,
        question_id=None,
        parent_turn_id=primary.id,
        sequence=2,
        turn_type=TurnType.FOLLOW_UP,
        question_content="请补充量化结果",
        status=TurnStatus.COMPLETED,
        follow_up_depth=1,
        created_at=datetime.now(UTC),
        answered_at=datetime.now(UTC),
        evaluated_at=datetime.now(UTC),
    )
    repository.turns[session.id] = [primary, follow_up]
    repository.answers[primary.id] = InterviewAnswer(
        id=uuid4(),
        turn_id=primary.id,
        session_id=session.id,
        user_id=user_id,
        content="我设计了异步架构并完成上线验证。",
        request_id="report-answer-1",
        created_at=datetime.now(UTC),
    )
    repository.answers[follow_up.id] = InterviewAnswer(
        id=uuid4(),
        turn_id=follow_up.id,
        session_id=session.id,
        user_id=user_id,
        content="上线后延迟降低了三十个百分点。",
        request_id="report-answer-2",
        created_at=datetime.now(UTC),
    )
    repository.evaluations[primary.id] = _evaluation(primary.id, 80)
    repository.evaluations[follow_up.id] = _evaluation(follow_up.id, 60, "补充结果")
    return repository, user_id, session.id


class FakeReportRepository:
    def __init__(self) -> None:
        self.reports: dict[UUID, InterviewReport] = {}
        self.items: dict[UUID, list[InterviewReportItem]] = {}

    async def create_pending(self, session_id: UUID, user_id: UUID) -> InterviewReport:
        existing = next(
            (report for report in self.reports.values() if report.session_id == session_id), None
        )
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        report = InterviewReport(
            id=uuid4(),
            session_id=session_id,
            user_id=user_id,
            status=ReportStatus.PENDING,
            overall_score=0,
            technical_score=0,
            relevance_score=0,
            clarity_score=0,
            depth_score=0,
            radar_data=[],
            strengths=[],
            weaknesses=[],
            suggested_improvements=[],
            summary="",
            action_plan=[],
            recommended_level=None,
            aggregation_version="pending",
            prompt_version=None,
            generated_by=ReportGeneratedBy.RULES,
            failure_code=None,
            failure_message=None,
            created_at=now,
            updated_at=now,
            completed_at=None,
        )
        self.reports[report.id] = report
        return report

    async def claim_generation(
        self, report_id: UUID, user_id: UUID
    ) -> tuple[InterviewReport, bool]:
        report = self.reports[report_id]
        if report.user_id != user_id or report.status in {
            ReportStatus.READY,
            ReportStatus.GENERATING,
        }:
            return report, False
        report.status = ReportStatus.GENERATING
        return report, True

    async def get_for_user(self, report_id: UUID, user_id: UUID) -> InterviewReport | None:
        report = self.reports.get(report_id)
        return report if report and report.user_id == user_id else None

    async def get_by_session(self, session_id: UUID, user_id: UUID) -> InterviewReport | None:
        return next(
            (
                report
                for report in self.reports.values()
                if report.session_id == session_id and report.user_id == user_id
            ),
            None,
        )

    async def list_for_user(
        self, user_id: UUID, current: int, size: int
    ) -> tuple[list[InterviewReport], int]:
        values = [report for report in self.reports.values() if report.user_id == user_id]
        start = (current - 1) * size
        return values[start : start + size], len(values)

    async def list_items(self, report_id: UUID, user_id: UUID) -> list[InterviewReportItem]:
        report = await self.get_for_user(report_id, user_id)
        return list(self.items.get(report_id, [])) if report else []

    async def persist_ready(
        self, report_id: UUID, user_id: UUID, *, scores, radar_data=None, **kwargs
    ):
        del radar_data
        report = self.reports[report_id]
        report.status = ReportStatus.READY
        report.overall_score = scores.overall_score
        report.technical_score = scores.technical_score
        report.relevance_score = scores.relevance_score
        report.clarity_score = scores.clarity_score
        report.depth_score = scores.depth_score
        report.radar_data = list(scores.radar_data)
        for field in (
            "strengths",
            "weaknesses",
            "suggested_improvements",
            "summary",
            "action_plan",
            "recommended_level",
            "aggregation_version",
            "prompt_version",
            "generated_by",
        ):
            value = kwargs[field]
            setattr(report, field, value if field != "generated_by" else value)
        report.completed_at = datetime.now(UTC)
        self.items[report_id] = list(kwargs["items"])
        return report

    async def mark_failed(
        self, report_id: UUID, user_id: UUID, failure_code: str, failure_message: str
    ) -> InterviewReport:
        report = self.reports[report_id]
        report.status = ReportStatus.FAILED
        report.failure_code = failure_code
        report.failure_message = failure_message
        self.items[report_id] = []
        return report


def _service(
    *, narrative: FakeInterviewReportNarrativeGenerator | None = None
) -> tuple[InterviewReportService, FakeReportRepository, InMemoryInterviewRepository, UUID, UUID]:
    interview_repository, user_id, session_id = _completed_interview()
    report_repository = FakeReportRepository()
    service = InterviewReportService(
        interview_repository,
        report_repository,
        narrative or FakeInterviewReportNarrativeGenerator(),
        FakeTaskQueue(),
        Settings(),
    )
    return service, report_repository, interview_repository, user_id, session_id


def test_score_aggregator_uses_primary_and_follow_up_weights() -> None:
    primary = InterviewTurn(
        id=uuid4(),
        session_id=uuid4(),
        question_id=None,
        parent_turn_id=None,
        sequence=1,
        turn_type=TurnType.PRIMARY,
        question_content="q",
        status=TurnStatus.COMPLETED,
        follow_up_depth=0,
        created_at=datetime.now(UTC),
        answered_at=None,
        evaluated_at=None,
    )
    follow_up = InterviewTurn(
        id=uuid4(),
        session_id=primary.session_id,
        question_id=None,
        parent_turn_id=primary.id,
        sequence=2,
        turn_type=TurnType.FOLLOW_UP,
        question_content="f",
        status=TurnStatus.COMPLETED,
        follow_up_depth=1,
        created_at=datetime.now(UTC),
        answered_at=None,
        evaluated_at=None,
    )
    result = InterviewScoreAggregator().aggregate(
        [(primary, _evaluation(primary.id, 80)), (follow_up, _evaluation(follow_up.id, 60))]
    )
    assert result.technical_score == 73
    assert result.overall_score == 73
    assert [item["dimension"] for item in result.radar_data] == [
        "technical",
        "relevance",
        "clarity",
        "depth",
    ]


def test_invalid_report_weights_are_rejected() -> None:
    with pytest.raises(ValueError):
        InterviewScoreAggregator(ReportAggregationWeights(technical=0.5))
    with pytest.raises(ValueError):
        InterviewScoreAggregator(ReportAggregationWeights(primary_turn=0, follow_up_turn=0))


@pytest.mark.asyncio
async def test_completed_interview_generates_immutable_snapshot_and_is_idempotent() -> None:
    narrative = FakeInterviewReportNarrativeGenerator()
    service, reports, interview_repository, user_id, session_id = _service(narrative=narrative)
    first = await service.generate(user_id, session_id)
    second = await service.generate(user_id, session_id)
    assert first.report.id == second.report.id
    assert first.report.status == ReportStatus.READY
    assert narrative.calls == 1
    assert [item.sequence for item in first.items] == [1, 2]
    assert first.items[0].sources[0]["sourceId"] == "[S1]"
    assert first.items[0].sources[0]["fileName"] == "resume.pdf"
    interview_repository.questions[session_id][0].citations.clear()
    reloaded = await service.get_by_session(user_id, session_id)
    assert reloaded.items[0].sources[0]["sourceId"] == "[S1]"


@pytest.mark.asyncio
async def test_narrative_failure_uses_rule_based_ready_report() -> None:
    narrative = FakeInterviewReportNarrativeGenerator(error=RuntimeError("provider unavailable"))
    service, reports, _, user_id, session_id = _service(narrative=narrative)
    detail = await service.generate(user_id, session_id)
    assert detail.report.status == ReportStatus.READY
    assert detail.report.generated_by == ReportGeneratedBy.RULES
    assert reports.reports[detail.report.id].summary
    assert narrative.calls == 1


@pytest.mark.asyncio
async def test_uncompleted_interview_cannot_generate_report() -> None:
    service, _, interview_repository, user_id, session_id = _service()
    interview_repository.sessions[session_id].status = InterviewStatus.IN_PROGRESS
    with pytest.raises(ReportSessionNotCompletedError):
        await service.generate(user_id, session_id)


@pytest.mark.asyncio
async def test_other_user_cannot_generate_or_view_report() -> None:
    service, _, _, _, session_id = _service()
    with pytest.raises(InterviewNotFoundError):
        await service.generate(uuid4(), session_id)


def test_report_api_requires_authentication_and_returns_paged_contract() -> None:
    service, _, _, user_id, session_id = _service()
    user = User(
        id=user_id,
        username="report-user",
        email="report@example.com",
        password_hash="hidden",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    try:
        with TestClient(app) as client:
            assert client.get("/api/xunzhi/v1/interview/reports").status_code == 401
            app.dependency_overrides[get_current_user] = lambda: user
            app.dependency_overrides[get_interview_report_service] = lambda: service
            generated = client.post(
                f"/api/xunzhi/v1/interview/sessions/{session_id}/report",
                headers={"Authorization": "Bearer test"},
            )
            assert generated.status_code == 200
            assert generated.json()["status"] == "READY"
            assert generated.json()["items"][0]["sequence"] == 1
            page = client.get(
                "/api/xunzhi/v1/interview/reports?current=1&size=10",
                headers={"Authorization": "Bearer test"},
            )
            assert page.status_code == 200
            assert page.json()["total"] == 1
    finally:
        app.dependency_overrides.clear()
