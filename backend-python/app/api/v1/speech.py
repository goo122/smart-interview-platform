"""Authenticated speech capability and streaming endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket

from app.modules.auth.dependencies import get_current_user, get_current_websocket_user
from app.modules.auth.domain import User
from app.modules.speech.dependencies import (
    get_speech_to_text_service,
    get_websocket_speech_to_text_service,
)
from app.modules.speech.schemas import SpeechCapabilitiesResponse
from app.modules.speech.service import SpeechToTextService

capabilities_router = APIRouter(prefix="/xunzhi/v1/speech", tags=["speech"])
audio_router = APIRouter(tags=["speech"])


@capabilities_router.get("/capabilities", response_model=SpeechCapabilitiesResponse)
async def speech_capabilities(
    _current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[SpeechToTextService, Depends(get_speech_to_text_service)],
) -> SpeechCapabilitiesResponse:
    return SpeechCapabilitiesResponse.from_domain(service.capabilities())


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
