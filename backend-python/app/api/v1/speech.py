"""Authenticated speech capability and streaming endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, WebSocket

from app.modules.auth.dependencies import get_current_user, get_current_websocket_user
from app.modules.auth.domain import User
from app.modules.speech.dependencies import (
    get_speech_to_text_service,
    get_websocket_speech_to_text_service,
)
from app.modules.speech.schemas import SpeechCapabilitiesResponse
from app.modules.speech.service import SpeechToTextService
from app.modules.speech.tts_dependencies import get_text_to_speech_service
from app.modules.speech.tts_schemas import (
    TextToSpeechRequestSchema,
    TtsCapabilitiesResponse,
    TtsTaskResponse,
)
from app.modules.speech.tts_service import TextToSpeechService

capabilities_router = APIRouter(prefix="/xunzhi/v1/speech", tags=["speech"])
audio_router = APIRouter(tags=["speech"])
tts_router = APIRouter(prefix="/xunzhi/v1/xunfei/tts", tags=["speech"])


@capabilities_router.get("/capabilities", response_model=SpeechCapabilitiesResponse)
async def speech_capabilities(
    _current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[SpeechToTextService, Depends(get_speech_to_text_service)],
) -> SpeechCapabilitiesResponse:
    return SpeechCapabilitiesResponse.from_domain(service.capabilities())


@capabilities_router.get("/tts/capabilities", response_model=TtsCapabilitiesResponse)
async def text_to_speech_capabilities(
    _current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[TextToSpeechService, Depends(get_text_to_speech_service)],
    response: Response,
) -> TtsCapabilitiesResponse:
    response.headers["Cache-Control"] = "no-store"
    return TtsCapabilitiesResponse.from_domain(service.capabilities())


@tts_router.post("/synthesize", response_model=TtsTaskResponse)
async def synthesize_text_to_speech(
    payload: TextToSpeechRequestSchema,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[TextToSpeechService, Depends(get_text_to_speech_service)],
    response: Response,
) -> TtsTaskResponse:
    response.headers["Cache-Control"] = "no-store"
    record = await service.synthesize(current_user.id, payload)
    return TtsTaskResponse.from_domain(record)


@tts_router.post("/tasks", response_model=TtsTaskResponse)
async def create_text_to_speech_task(
    payload: TextToSpeechRequestSchema,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[TextToSpeechService, Depends(get_text_to_speech_service)],
    response: Response,
) -> TtsTaskResponse:
    response.headers["Cache-Control"] = "no-store"
    record = await service.create_task(current_user.id, payload)
    return TtsTaskResponse.from_domain(record)


@tts_router.get("/tasks/{task_id}", response_model=TtsTaskResponse)
async def get_text_to_speech_task(
    task_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[TextToSpeechService, Depends(get_text_to_speech_service)],
    response: Response,
) -> TtsTaskResponse:
    response.headers["Cache-Control"] = "no-store"
    record = await service.get_task(current_user.id, task_id)
    return TtsTaskResponse.from_domain(record)


@audio_router.websocket("/xunzhi/v1/xunfei/audio-to-text/{user_id}")
async def audio_to_text(
    websocket: WebSocket,
    user_id: str,
    _current_user: Annotated[User, Depends(get_current_websocket_user)],
    service: Annotated[
        SpeechToTextService, Depends(get_websocket_speech_to_text_service)
    ],
) -> None:
    await service.handle_websocket(websocket)
