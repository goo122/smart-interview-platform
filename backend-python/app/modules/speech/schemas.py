"""Public, secret-free speech capability schema."""

from pydantic import BaseModel, ConfigDict, Field

from app.modules.speech.service import SpeechCapabilities


class SpeechCapabilitiesResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    available: bool
    provider: str
    audio_format: str = Field(alias="audioFormat")
    sample_rate: int = Field(alias="sampleRate")
    channels: int
    supported_audio_formats: list[str] = Field(alias="supportedAudioFormats")
    supported_sample_rates: list[int] = Field(alias="supportedSampleRates")
    max_session_seconds: int = Field(alias="maxSessionSeconds")
    max_frame_bytes: int = Field(alias="maxFrameBytes")
    max_audio_bytes: int = Field(alias="maxAudioBytes")

    @classmethod
    def from_domain(cls, capabilities: SpeechCapabilities) -> "SpeechCapabilitiesResponse":
        return cls(
            available=capabilities.available,
            provider=capabilities.provider,
            audioFormat=capabilities.audio_format,
            sampleRate=capabilities.sample_rate,
            channels=capabilities.channels,
            supportedAudioFormats=list(capabilities.supported_audio_formats),
            supportedSampleRates=list(capabilities.supported_sample_rates),
            maxSessionSeconds=capabilities.max_session_seconds,
            maxFrameBytes=capabilities.max_frame_bytes,
            maxAudioBytes=capabilities.max_audio_bytes,
        )
