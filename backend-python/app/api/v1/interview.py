import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from fastapi.responses import Response, StreamingResponse

from app.modules.auth.dependencies import get_current_user
from app.modules.auth.domain import User
from app.modules.interview.answer_service import InterviewAnswerService
from app.modules.interview.demeanor_service import DemeanorAnalysisService
from app.modules.interview.dependencies import (
    get_demeanor_analysis_service,
    get_interview_answer_service,
    get_interview_service,
)
from app.modules.interview.schemas import (
    CreateInterviewSessionRequest,
    DemeanorAnalysisCapabilitiesResponse,
    DemeanorEvaluationResponse,
    InterviewConversationResponse,
    InterviewPageResponse,
    InterviewQuestionResponse,
    InterviewSessionResponse,
    InterviewTurnResponse,
    ResolveInterviewRoleRequest,
    ResolveInterviewRoleResponse,
    SubmitInterviewAnswerRequest,
    SubmitInterviewAnswerResponse,
)
from app.modules.interview.service import InterviewService
from app.modules.knowledge.dependencies import get_knowledge_service
from app.modules.knowledge.service import KnowledgeService
from app.modules.report.dependencies import get_interview_report_service
from app.modules.report.schemas import (
    InterviewReportPageResponse,
    InterviewReportResponse,
)
from app.modules.report.service import InterviewReportService

router = APIRouter(prefix="/xunzhi/v1/interview", tags=["interview"])
logger = logging.getLogger(__name__)


@router.get(
    "/demeanor/capabilities",
    response_model=DemeanorAnalysisCapabilitiesResponse,
)
async def demeanor_capabilities(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[DemeanorAnalysisService, Depends(get_demeanor_analysis_service)],
) -> DemeanorAnalysisCapabilitiesResponse:
    """Expose safe capability metadata so the browser can disable unsupported polling."""

    del current_user
    capabilities = service.capabilities()
    return DemeanorAnalysisCapabilitiesResponse(
        available=capabilities.available,
        provider=capabilities.provider,
        maxImageBytes=capabilities.max_image_bytes,
        maxPixels=capabilities.max_pixels,
        minIntervalSeconds=capabilities.min_interval_seconds,
        analysisVersion=capabilities.analysis_version,
    )


@router.post(
    "/resolve-role",
    response_model=ResolveInterviewRoleResponse,
)
async def resolve_role(
    payload: ResolveInterviewRoleRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InterviewService, Depends(get_interview_service)],
) -> ResolveInterviewRoleResponse:
    """Infer the interview direction from the user's ready resume."""

    fallback_title = "综合岗位"
    fallback_description = "结合候选人简历中的经历、技能和项目成果进行综合面试评估。"
    try:
        inference = await service.infer_resume_role(current_user.id, payload.knowledge_base_id)
    except RuntimeError:
        return ResolveInterviewRoleResponse(
            jobTitle=fallback_title,
            jobDescription=fallback_description,
            confidence=None,
            inferred=False,
            inferenceVersion="resume-role-v1",
        )
    title = inference.recommended_job_title.strip() or fallback_title
    return ResolveInterviewRoleResponse(
        jobTitle=title,
        jobDescription=f"围绕{title}的岗位职责、核心技能、项目经验和问题解决能力进行综合评估。",
        confidence=inference.confidence,
        inferred=True,
        inferenceVersion="resume-role-v1",
    )


@router.post(
    "/sessions",
    response_model=InterviewSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    payload: CreateInterviewSessionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InterviewService, Depends(get_interview_service)],
) -> InterviewSessionResponse:
    started_at = time.perf_counter()
    session = await service.create_session(
        user_id=current_user.id,
        knowledge_base_id=payload.knowledge_base_id,
        job_title=payload.job_title,
        job_description=payload.job_description,
        interview_type=payload.interview_type,
        difficulty=payload.difficulty,
        question_count=payload.question_count,
        request_id=payload.request_id,
    )
    evaluation = await service.get_resume_evaluation(current_user.id, session.id)
    response_ms = round((time.perf_counter() - started_at) * 1000, 2)
    logger.info(
        "Interview start response completed interview_start_response_ms=%s",
        response_ms,
        extra={
            "session_id": str(session.id),
            "user_id": str(current_user.id),
            "interview_start_response_ms": response_ms,
            "status": session.status.value,
        },
    )
    return InterviewSessionResponse.from_domain(session, evaluation)


@router.get("/sessions", response_model=InterviewPageResponse[InterviewSessionResponse])
async def list_sessions(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InterviewService, Depends(get_interview_service)],
    current: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
) -> InterviewPageResponse[InterviewSessionResponse]:
    sessions, total = await service.list_sessions(current_user.id, current, size)
    return InterviewPageResponse.build(
        [InterviewSessionResponse.from_domain(session) for session in sessions],
        total,
        current,
        size,
    )


@router.get(
    "/conversations",
    response_model=InterviewPageResponse[InterviewConversationResponse],
)
async def list_conversations(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InterviewService, Depends(get_interview_service)],
    current: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    keyword: str | None = Query(default=None, max_length=200),
) -> InterviewPageResponse[InterviewConversationResponse]:
    sessions, total = await service.list_conversations(
        current_user.id,
        current,
        size,
        status_filter,
        keyword,
    )
    return InterviewPageResponse.build(
        [InterviewConversationResponse.from_domain(session) for session in sessions],
        total,
        current,
        size,
    )


@router.get("/sessions/{session_id}", response_model=InterviewSessionResponse)
async def get_session(
    session_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InterviewService, Depends(get_interview_service)],
) -> InterviewSessionResponse:
    session = await service.get_session(current_user.id, session_id)
    evaluation = await service.get_resume_evaluation(current_user.id, session_id)
    return InterviewSessionResponse.from_domain(session, evaluation)


@router.get("/sessions/{session_id}/events/stream", response_class=StreamingResponse)
async def stream_preparation_events(
    session_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InterviewService, Depends(get_interview_service)],
) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        async for message in service.stream_preparation_events(
            current_user.id, session_id
        ):
            yield (
                f"id: {message['id']}\n"
                f"event: {message['event']}\n"
                f"data: {json.dumps(message['data'], ensure_ascii=False)}\n\n"
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/sessions/{session_id}/demeanor-evaluation",
    response_model=DemeanorEvaluationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def evaluate_demeanor(
    session_id: UUID,
    user_photo: Annotated[UploadFile, File(..., alias="userPhoto")],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[DemeanorAnalysisService, Depends(get_demeanor_analysis_service)],
) -> DemeanorEvaluationResponse:
    """Analyze one camera frame without persisting the original image."""

    image_bytes = await user_photo.read(service.max_image_bytes + 1)
    result = await service.analyze(
        user_id=current_user.id,
        session_id=session_id,
        image_bytes=image_bytes,
        mime_type=user_photo.content_type,
    )
    return DemeanorEvaluationResponse.from_domain(result)


@router.get(
    "/sessions/{session_id}/questions",
    response_model=list[InterviewQuestionResponse],
)
async def get_questions(
    session_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InterviewService, Depends(get_interview_service)],
) -> list[InterviewQuestionResponse]:
    questions = await service.get_questions(current_user.id, session_id)
    return [InterviewQuestionResponse.from_domain(question) for question in questions]


@router.post("/sessions/{session_id}/start", response_model=InterviewSessionResponse)
async def start_session(
    session_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InterviewService, Depends(get_interview_service)],
) -> InterviewSessionResponse:
    session = await service.start(current_user.id, session_id)
    evaluation = await service.get_resume_evaluation(current_user.id, session_id)
    return InterviewSessionResponse.from_domain(session, evaluation)


@router.post("/sessions/{session_id}/cancel", response_model=InterviewSessionResponse)
async def cancel_session(
    session_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InterviewService, Depends(get_interview_service)],
) -> InterviewSessionResponse:
    session = await service.cancel(current_user.id, session_id)
    evaluation = await service.get_resume_evaluation(current_user.id, session_id)
    return InterviewSessionResponse.from_domain(session, evaluation)


@router.post("/sessions/{session_id}/finish", response_model=InterviewSessionResponse)
async def finish_session(
    session_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InterviewService, Depends(get_interview_service)],
) -> InterviewSessionResponse:
    session = await service.finish(current_user.id, session_id)
    evaluation = await service.get_resume_evaluation(current_user.id, session_id)
    return InterviewSessionResponse.from_domain(session, evaluation)


@router.get("/sessions/{session_id}/resume/preview")
async def resume_preview(
    session_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    interview_service: Annotated[InterviewService, Depends(get_interview_service)],
    knowledge_service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
) -> Response:
    session = await interview_service.get_session(current_user.id, session_id)
    document = await knowledge_service.get_latest_ready_document(
        current_user.id, session.knowledge_base_id
    )
    content = await knowledge_service.read_document_content(current_user.id, document.id)
    return Response(content=content, media_type="application/pdf")


@router.get(
    "/sessions/{session_id}/current-turn",
    response_model=InterviewTurnResponse,
)
async def current_turn(
    session_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InterviewAnswerService, Depends(get_interview_answer_service)],
) -> InterviewTurnResponse:
    progress = await service.current_turn(current_user.id, session_id)
    return InterviewTurnResponse.from_progress(progress)


@router.post(
    "/sessions/{session_id}/answers",
    response_model=SubmitInterviewAnswerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_answer(
    session_id: UUID,
    payload: SubmitInterviewAnswerRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InterviewAnswerService, Depends(get_interview_answer_service)],
) -> SubmitInterviewAnswerResponse:
    progress = await service.submit_answer(
        user_id=current_user.id,
        session_id=session_id,
        turn_id=payload.turn_id,
        answer=payload.answer,
        request_id=payload.request_id,
    )
    next_turn = await service.next_turn_after_submission(
        current_user.id, session_id, progress.turn.id
    )
    return SubmitInterviewAnswerResponse(
        sessionId=progress.session.id,
        turnId=progress.turn.id,
        status=progress.turn.status.value,
        requestId=payload.request_id.strip(),
        nextTurn=InterviewTurnResponse.from_progress(next_turn) if next_turn else None,
    )


@router.get(
    "/sessions/{session_id}/turns",
    response_model=list[InterviewTurnResponse],
)
async def list_turns(
    session_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InterviewAnswerService, Depends(get_interview_answer_service)],
) -> list[InterviewTurnResponse]:
    turns = await service.list_turns(current_user.id, session_id)
    return [InterviewTurnResponse.from_progress(turn) for turn in turns]


@router.get("/sessions/{session_id}/turns/{turn_id}", response_model=InterviewTurnResponse)
async def get_turn(
    session_id: UUID,
    turn_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InterviewAnswerService, Depends(get_interview_answer_service)],
) -> InterviewTurnResponse:
    progress = await service.get_turn(current_user.id, turn_id, session_id)
    return InterviewTurnResponse.from_progress(progress)


@router.post(
    "/sessions/{session_id}/report",
    response_model=InterviewReportResponse,
)
async def generate_report(
    session_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InterviewReportService, Depends(get_interview_report_service)],
    response: Response,
    request: Request,
) -> InterviewReportResponse:
    report = await service.generate(
        current_user.id,
        session_id,
        getattr(request.state, "request_id", None),
    )
    if report.report.status.value in {"PENDING", "GENERATING"}:
        response.status_code = status.HTTP_202_ACCEPTED
    return InterviewReportResponse.from_detail(report)


@router.get(
    "/sessions/{session_id}/report",
    response_model=InterviewReportResponse,
)
async def get_session_report(
    session_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InterviewReportService, Depends(get_interview_report_service)],
) -> InterviewReportResponse:
    report = await service.get_by_session(current_user.id, session_id)
    return InterviewReportResponse.from_detail(report)


@router.get(
    "/reports",
    response_model=InterviewReportPageResponse[InterviewReportResponse],
)
async def list_reports(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InterviewReportService, Depends(get_interview_report_service)],
    current: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
) -> InterviewReportPageResponse[InterviewReportResponse]:
    reports, total = await service.list(current_user.id, current, size)
    return InterviewReportPageResponse.build(
        [InterviewReportResponse.from_detail(report) for report in reports],
        total,
        current,
        size,
    )


@router.get("/reports/{report_id}", response_model=InterviewReportResponse)
async def get_report(
    report_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InterviewReportService, Depends(get_interview_report_service)],
) -> InterviewReportResponse:
    report = await service.get(current_user.id, report_id)
    return InterviewReportResponse.from_detail(report)
