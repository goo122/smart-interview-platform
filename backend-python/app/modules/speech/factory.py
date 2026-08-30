"""Runtime selection for speech-to-text adapters."""

from app.core.config import Settings
from app.infrastructure.speech.fake import FakeSpeechToTextAdapter
from app.infrastructure.speech.unavailable import UnavailableSpeechToTextAdapter
from app.infrastructure.speech.xunfei import XunfeiSpeechToTextAdapter
from app.modules.speech.ports import SpeechToTextPort


class SpeechProviderConfigurationError(RuntimeError):
    """Raised when speech provider configuration is unsafe or incomplete."""


class SpeechToTextProviderFactory:
    @classmethod
    def build(cls, settings: Settings) -> SpeechToTextPort:
        provider = settings.speech_to_text_provider
        environment = settings.app_env.strip().lower()
        if environment == "production" and provider == "fake":
            raise SpeechProviderConfigurationError(
                "Fake speech providers are not allowed in production"
            )
        if provider == "fake":
            return FakeSpeechToTextAdapter()
        if provider == "xunfei":
            return XunfeiSpeechToTextAdapter(
                app_id=settings.xunfei_asr_app_id,
                api_key=settings.xunfei_asr_api_key,
                api_secret=settings.xunfei_asr_api_secret,
                endpoint=settings.xunfei_asr_url,
                timeout_seconds=settings.ai_request_timeout_seconds,
            )
        return UnavailableSpeechToTextAdapter()
