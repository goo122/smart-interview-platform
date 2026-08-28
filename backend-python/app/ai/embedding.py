import hashlib
from collections.abc import Sequence
from typing import Any, Protocol, cast


class EmbeddingPort(Protocol):
    @property
    def dimensions(self) -> int: ...

    async def embed_documents(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...

    async def embed_query(self, text: str) -> Sequence[float]: ...


class FakeEmbedding:
    """Stable deterministic embeddings for tests; never calls an external service."""

    def __init__(self, dimensions: int = 1536, wrong_dimensions: int | None = None) -> None:
        self._dimensions = dimensions
        self.wrong_dimensions = wrong_dimensions
        self.batch_calls: list[tuple[str, ...]] = []
        self.query_calls: list[str] = []
        self.error: Exception | None = None

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed_documents(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        self.batch_calls.append(tuple(texts))
        if self.error is not None:
            raise self.error
        return [self._embed(text, self.wrong_dimensions or self._dimensions) for text in texts]

    async def embed_query(self, text: str) -> Sequence[float]:
        self.query_calls.append(text)
        if self.error is not None:
            raise self.error
        return self._embed(text, self._dimensions)

    @staticmethod
    def _embed(text: str, dimensions: int) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [((digest[index % len(digest)] / 255.0) * 2.0) - 1.0 for index in range(dimensions)]


class UnavailableEmbedding:
    def __init__(self, dimensions: int = 1536) -> None:
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed_documents(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        del texts
        raise RuntimeError("No embedding model is configured")

    async def embed_query(self, text: str) -> Sequence[float]:
        del text
        raise RuntimeError("No embedding model is configured")


class LangChainEmbeddingAdapter:
    """Adapter for a LangChain-compatible embeddings object."""

    def __init__(self, embeddings: Any, dimensions: int) -> None:
        self._embeddings = embeddings
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed_documents(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        result = self._embeddings.aembed_documents(list(texts))
        return cast(Sequence[Sequence[float]], await result)

    async def embed_query(self, text: str) -> Sequence[float]:
        return cast(Sequence[float], await self._embeddings.aembed_query(text))
