"""Safe application exceptions for speech recognition."""


class SpeechProviderUnavailableError(RuntimeError):
    """The selected provider is not configured or cannot be reached."""


class SpeechProviderProtocolError(RuntimeError):
    """The provider returned an invalid or unsupported response."""
