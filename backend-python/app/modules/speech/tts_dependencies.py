"""FastAPI dependency wiring for text-to-speech."""

from typing import cast

from fastapi import Request

from app.modules.speech.tts_service import TextToSpeechService


def get_text_to_speech_service(request: Request) -> TextToSpeechService:
    return cast(TextToSpeechService, request.app.state.text_to_speech_service)
