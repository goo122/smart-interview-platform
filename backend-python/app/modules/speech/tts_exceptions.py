"""Safe application and infrastructure errors for text-to-speech."""

from app.core.exceptions import AppError


class TextToSpeechProviderError(RuntimeError):
    """An infrastructure adapter could not complete synthesis."""


class TextToSpeechProviderUnavailable(RuntimeError):
    """The selected TTS provider is not configured or reachable."""


class InvalidTextToSpeechRequestError(AppError):
    status_code = 400
    code = "invalid_tts_request"


class TextToSpeechUnavailableError(AppError):
    status_code = 503
    code = "tts_provider_unavailable"


class TextToSpeechFailedError(AppError):
    status_code = 502
    code = "tts_provider_failed"


class TextToSpeechTaskNotFoundError(AppError):
    status_code = 404
    code = "tts_task_not_found"


class TextToSpeechIdempotencyConflictError(AppError):
    status_code = 409
    code = "tts_idempotency_conflict"


class TextToSpeechRateLimitError(AppError):
    status_code = 429
    code = "tts_rate_limited"
