from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from app.modules.knowledge.domain import StoredChunk


class VectorStorePort(Protocol):
    async def store_chunks(self, document_id: UUID, chunks: Sequence[StoredChunk]) -> None: ...

    async def delete_document(self, document_id: UUID) -> None: ...

    async def rollback(self) -> None: ...

    async def similarity_search(
        self, document_id: UUID, embedding: Sequence[float], limit: int = 5
    ) -> Sequence[StoredChunk]: ...
