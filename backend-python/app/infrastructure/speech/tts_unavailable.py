"""Safe TTS adapter used when no provider is configured."""

from app.modules.speech.tts_exceptions import TextToSpeechProviderUnavailable
from app.modules.speech.tts_ports import TextToSpeechRequest, TextToSpeechResult


class UnavailableTextToSpeechAdapter:
    provider_name = "unavailable"
    is_available = False
    supported_audio_formats = ("wav",)
    supported_voices = ()
    max_text_length = 0
    supports_streaming = False

    async def synthesize(self, _request: TextToSpeechRequest) -> TextToSpeechResult:
        raise TextToSpeechProviderUnavailable("Text-to-speech provider is not configured")
