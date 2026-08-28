from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from app.modules.knowledge.domain import RetrievedChunk
from app.modules.knowledge.exceptions import EmbeddingDimensionError


class RetrieverPort(Protocol):
    async def retrieve(
        self,
        *,
        user_id: UUID,
        knowledge_base_id: UUID,
        query_vector: Sequence[float],
        top_k: int,
        similarity_threshold: float,
    ) -> Sequence[RetrievedChunk]: ...


class FakeRetriever:
    """Deterministic retriever double for unit and API tests."""

    def __init__(
        self,
        chunks: Sequence[RetrievedChunk] = (),
        dimensions: int = 1536,
        error: Exception | None = None,
    ) -> None:
        self.chunks = tuple(chunks)
        self.dimensions = dimensions
        self.error = error
        self.calls: list[tuple[UUID, UUID, int, float]] = []

    async def retrieve(
        self,
        *,
        user_id: UUID,
        knowledge_base_id: UUID,
        query_vector: Sequence[float],
        top_k: int,
        similarity_threshold: float,
    ) -> Sequence[RetrievedChunk]:
        if len(query_vector) != self.dimensions:
            raise EmbeddingDimensionError("Query embedding dimensions are invalid")
        if self.error is not None:
            raise self.error
        self.calls.append((user_id, knowledge_base_id, top_k, similarity_threshold))
        return tuple(
            item
            for item in sorted(self.chunks, key=lambda chunk: chunk.score, reverse=True)
            if item.score >= similarity_threshold
        )[:top_k]
