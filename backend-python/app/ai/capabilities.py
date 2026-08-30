"""Provider capability metadata shared by runtime wiring and services."""

from __future__ import annotations


def embedding_batch_limit(provider: str, model: str | None) -> int | None:
    """Return a known provider/model document batch limit.

    ``None`` means that this adapter has no application-level limit.  The
    DashScope OpenAI-compatible ``text-embedding-v4`` endpoint currently
    accepts at most ten texts in one request, so the limit is kept as provider
    capability metadata rather than duplicated in import code.
    """

    if provider == "openai_compatible" and model == "text-embedding-v4":
        return 10
    return None
