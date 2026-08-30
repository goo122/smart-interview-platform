"""Safe no-provider speech adapter."""

from collections.abc import Sequence

from app.modules.speech.exceptions import SpeechProviderUnavailableError
from app.modules.speech.ports import SpeechAudioFormat, SpeechToTextSession


class UnavailableSpeechToTextAdapter:
    provider_name = "unavailable"
    is_available = False

    @property
    def supported_audio_formats(self) -> Sequence[str]:
        return ("pcm_s16le",)

    async def create_session(self, audio_format: SpeechAudioFormat) -> SpeechToTextSession:
        raise SpeechProviderUnavailableError("Speech-to-text provider is not configured")
