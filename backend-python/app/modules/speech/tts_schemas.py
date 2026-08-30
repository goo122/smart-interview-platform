"""HTTP schemas for the backwards-compatible Xunfei TTS routes."""

from pydantic import BaseModel, ConfigDict, Field

from app.modules.speech.tts_service import TtsCapabilities, TtsSynthesisRecord


class TextToSpeechRequestSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    text: str
    vcn: str | None = None
    language: str | None = None
    speed: int | None = Field(default=None, ge=0, le=100)
    volume: int | None = Field(default=None, ge=0, le=100)
    pitch: int | None = Field(default=None, ge=0, le=100)
    rhy: int | None = Field(default=None, ge=0, le=1)
    audio_encoding: str | None = Field(default=None, alias="audioEncoding")
    sample_rate: int | None = Field(default=None, alias="sampleRate", ge=8000, le=48000)
    timeout_seconds: float | None = Field(
        default=None, alias="timeoutSeconds", gt=0, le=300
    )
    poll_interval_ms: int | None = Field(
        default=None, alias="pollIntervalMs", ge=100, le=30000
    )
    request_id: str | None = Field(default=None, alias="requestId", min_length=1, max_length=128)


class TtsTaskResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sid: str | None = None
    task_id: str = Field(alias="taskId")
    task_status: str = Field(default="5", alias="taskStatus")
    code: int = 0
    message: str = "success"
    audio_base64: str = Field(alias="audioBase64")
    audio_url: None = Field(default=None, alias="audioUrl")
    pybuf_content: None = Field(default=None, alias="pybufContent")
    pybuf_url: None = Field(default=None, alias="pybufUrl")
    audio_format: str = Field(alias="audioFormat")
    content_type: str = Field(alias="contentType")
    completed: bool = True
    success: bool = True

    @classmethod
    def from_domain(cls, record: TtsSynthesisRecord) -> "TtsTaskResponse":
        return cls(
            taskId=str(record.task_id),
            audioBase64=record.audio_base64,
            audioFormat=record.audio_format,
            contentType=record.content_type,
        )


class TtsCapabilitiesResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    available: bool
    provider: str
    supported_audio_formats: list[str] = Field(alias="supportedAudioFormats")
    supported_voices: list[str] = Field(alias="supportedVoices")
    max_text_length: int = Field(alias="maxTextLength")
    supports_streaming: bool = Field(alias="supportsStreaming")

    @classmethod
    def from_domain(cls, capabilities: TtsCapabilities) -> "TtsCapabilitiesResponse":
        return cls(
            available=capabilities.available,
            provider=capabilities.provider,
            supportedAudioFormats=list(capabilities.supported_audio_formats),
            supportedVoices=list(capabilities.supported_voices),
            maxTextLength=capabilities.max_text_length,
            supportsStreaming=capabilities.supports_streaming,
        )
