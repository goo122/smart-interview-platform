"""Runtime selection for text-to-speech adapters."""

from app.core.config import Settings
from app.infrastructure.speech.tts_fake import FakeTextToSpeechAdapter
from app.infrastructure.speech.tts_unavailable import UnavailableTextToSpeechAdapter
from app.infrastructure.speech.tts_xunfei import XunfeiTextToSpeechAdapter
from app.modules.speech.tts_ports import TextToSpeechPort


class TextToSpeechProviderFactory:
    @classmethod
    def build(cls, settings: Settings) -> TextToSpeechPort:
        provider = settings.text_to_speech_provider
        if settings.app_env.strip().lower() == "production" and provider == "fake":
            raise RuntimeError("Fake text-to-speech providers are not allowed in production")
        if provider == "fake":
            return FakeTextToSpeechAdapter()
        if provider == "xunfei":
            return XunfeiTextToSpeechAdapter(
                app_id=settings.xunfei_tts_app_id,
                api_key=settings.xunfei_tts_api_key,
                api_secret=settings.xunfei_tts_api_secret,
                endpoint=settings.xunfei_tts_url,
                max_audio_bytes=settings.tts_max_audio_bytes,
            )
        return UnavailableTextToSpeechAdapter()
