"""FastAPI dependency wiring for speech capabilities and websocket sessions."""

from typing import cast

from fastapi import Request, WebSocket

from app.modules.speech.service import SpeechToTextService


def get_speech_to_text_service(request: Request) -> SpeechToTextService:
    return cast(SpeechToTextService, request.app.state.speech_to_text_service)


def get_websocket_speech_to_text_service(websocket: WebSocket) -> SpeechToTextService:
    return cast(SpeechToTextService, websocket.app.state.speech_to_text_service)
