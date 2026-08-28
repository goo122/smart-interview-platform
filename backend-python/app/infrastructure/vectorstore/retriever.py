from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.domain import DocumentStatus, RetrievedChunk
from app.modules.knowledge.exceptions import EmbeddingDimensionError
from app.modules.knowledge.models import (
    KnowledgeBaseModel,
    KnowledgeChunkModel,
    KnowledgeDocumentModel,
)


class PgVectorRetriever:
    """Scoped cosine-similarity retrieval backed by PostgreSQL/pgvector."""

    def __init__(self, session: AsyncSession, dimensions: int = 1536) -> None:
        self._session = session
        self._dimensions = dimensions

    async def retrieve(
        self,
        *,
        user_id: UUID,
        knowledge_base_id: UUID,
        query_vector: Sequence[float],
        top_k: int,
        similarity_threshold: float,
    ) -> Sequence[RetrievedChunk]:
        if len(query_vector) != self._dimensions:
            raise EmbeddingDimensionError("Query embedding dimensions are invalid")
        bounded_top_k = max(1, min(top_k, 100))
        distance = KnowledgeChunkModel.embedding.cosine_distance(list(query_vector))
        similarity = (1 - distance).label("similarity")
        query: Select[tuple[KnowledgeChunkModel, KnowledgeDocumentModel, float]] = (
            select(KnowledgeChunkModel, KnowledgeDocumentModel, similarity)
            .join(
                KnowledgeDocumentModel,
                KnowledgeDocumentModel.id == KnowledgeChunkModel.document_id,
            )
            .join(
                KnowledgeBaseModel,
                KnowledgeBaseModel.id == KnowledgeDocumentModel.knowledge_base_id,
            )
            .where(
                KnowledgeBaseModel.id == knowledge_base_id,
                KnowledgeBaseModel.user_id == user_id,
                KnowledgeDocumentModel.status == DocumentStatus.READY.value,
                similarity >= similarity_threshold,
            )
            .order_by(similarity.desc())
            .limit(bounded_top_k)
        )
        result = await self._session.execute(query)
        return [
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document_name=document.original_filename,
                page_number=chunk.page_number,
                content=chunk.content,
                score=float(score),
            )
            for chunk, document, score in result.all()
        ]
