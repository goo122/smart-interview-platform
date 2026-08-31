from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.report import (
    InterviewReportNarrativePort,
    RuleBasedInterviewReportNarrativeGenerator,
)
from app.core.config import Settings, get_settings
from app.modules.auth.dependencies import get_db_session
from app.modules.interview.dependencies import get_interview_repository
from app.modules.interview.repository import InterviewRepository
from app.modules.report.repository import (
    InterviewReportRepository,
    SqlAlchemyInterviewReportRepository,
)
from app.modules.report.service import InterviewReportService
from app.workers.queue import InterviewReportTaskQueuePort


async def get_interview_report_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InterviewReportRepository:
    return SqlAlchemyInterviewReportRepository(session)


def get_interview_report_narrative(request: Request) -> InterviewReportNarrativePort:
    return cast(
        InterviewReportNarrativePort,
        getattr(
            request.app.state,
            "interview_report_narrative",
            RuleBasedInterviewReportNarrativeGenerator(),
        ),
    )


def get_interview_report_task_queue(request: Request) -> InterviewReportTaskQueuePort:
    """Return the ARQ queue dedicated to report generation."""

    return cast(
        InterviewReportTaskQueuePort,
        request.app.state.interview_report_task_queue,
    )


def get_interview_report_service(
    interview_repository: Annotated[
        InterviewRepository, Depends(get_interview_repository)
    ],
    report_repository: Annotated[
        InterviewReportRepository, Depends(get_interview_report_repository)
    ],
    narrative: Annotated[
        InterviewReportNarrativePort, Depends(get_interview_report_narrative)
    ],
    task_queue: Annotated[
        InterviewReportTaskQueuePort, Depends(get_interview_report_task_queue)
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> InterviewReportService:
    return InterviewReportService(
        interview_repository,
        report_repository,
        narrative,
        task_queue,
        settings,
    )
