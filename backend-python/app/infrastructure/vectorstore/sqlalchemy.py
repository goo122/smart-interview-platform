from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.domain import StoredChunk
from app.modules.knowledge.models import KnowledgeChunkModel


class SqlAlchemyVectorStore:
    def __init__(self, session: AsyncSession, dimensions: int = 1536) -> None:
        self._session = session
        self._dimensions = dimensions

    async def store_chunks(self, document_id: UUID, chunks: Sequence[StoredChunk]) -> None:
        for chunk in chunks:
            if len(chunk.embedding) != self._dimensions:
                raise ValueError("Embedding dimensions do not match configured vector size")
            self._session.add(
                KnowledgeChunkModel(
                    document_id=document_id,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    content=chunk.content,
                    token_count=chunk.token_count,
                    content_hash=chunk.content_hash,
                    embedding=list(chunk.embedding),
                )
            )
        await self._session.flush()

    async def delete_document(self, document_id: UUID) -> None:
        await self._session.execute(
            delete(KnowledgeChunkModel).where(KnowledgeChunkModel.document_id == document_id)
        )
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    async def similarity_search(
        self, document_id: UUID, embedding: Sequence[float], limit: int = 5
    ) -> Sequence[StoredChunk]:
        if len(embedding) != self._dimensions:
            raise ValueError("Embedding dimensions do not match configured vector size")
        result = await self._session.execute(
            select(KnowledgeChunkModel)
            .where(KnowledgeChunkModel.document_id == document_id)
            .order_by(KnowledgeChunkModel.embedding.cosine_distance(list(embedding)))
            .limit(limit)
        )
        return [_chunk_to_domain(row) for row in result.scalars().all()]


def _chunk_to_domain(row: KnowledgeChunkModel) -> StoredChunk:
    return StoredChunk(
        chunk_index=row.chunk_index,
        page_number=row.page_number,
        content=row.content,
        token_count=row.token_count,
        content_hash=row.content_hash,
        embedding=tuple(float(value) for value in row.embedding),
    )
