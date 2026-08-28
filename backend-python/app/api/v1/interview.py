from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.modules.auth.dependencies import get_current_user
from app.modules.auth.domain import User
from app.modules.interview.answer_service import InterviewAnswerService
from app.modules.interview.dependencies import (
    get_interview_answer_service,
    get_interview_service,
)
from app.modules.interview.schemas import (
    CreateInterviewSessionRequest,
    InterviewPageResponse,
    InterviewQuestionResponse,
    InterviewSessionResponse,
    InterviewTurnResponse,
    SubmitInterviewAnswerRequest,
    SubmitInterviewAnswerResponse,
)
from app.modules.interview.service import InterviewService

router = APIRouter(prefix="/xunzhi/v1/interview", tags=["interview"])


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
    return InterviewSessionResponse.from_domain(session)


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


@router.get("/sessions/{session_id}", response_model=InterviewSessionResponse)
async def get_session(
    session_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InterviewService, Depends(get_interview_service)],
) -> InterviewSessionResponse:
    session = await service.get_session(current_user.id, session_id)
    return InterviewSessionResponse.from_domain(session)


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
    return InterviewSessionResponse.from_domain(session)


@router.post("/sessions/{session_id}/cancel", response_model=InterviewSessionResponse)
async def cancel_session(
    session_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InterviewService, Depends(get_interview_service)],
) -> InterviewSessionResponse:
    session = await service.cancel(current_user.id, session_id)
    return InterviewSessionResponse.from_domain(session)


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
    return SubmitInterviewAnswerResponse(
        sessionId=progress.session.id,
        turnId=progress.turn.id,
        status=progress.turn.status.value,
        requestId=payload.request_id.strip(),
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
