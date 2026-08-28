from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.ai.embedding import EmbeddingPort
from app.core.config import Settings
from app.core.exceptions import RagNoResultsError
from app.modules.knowledge.context import AssembledContext, ContextAssembler, ContextCitation
from app.modules.knowledge.exceptions import EmbeddingDimensionError, KnowledgeBaseNotFoundError
from app.modules.knowledge.repository import KnowledgeRepository
from app.modules.knowledge.retrieval import RetrieverPort


@dataclass(frozen=True, slots=True)
class RagContext:
    prompt: str
    citations: tuple[ContextCitation, ...]


class ContextProvider(Protocol):
    async def validate_knowledge_base(self, user_id: UUID, knowledge_base_id: UUID) -> None: ...

    async def build(
        self,
        *,
        user_id: UUID,
        knowledge_base_id: UUID,
        query: str,
        top_k: int | None,
        similarity_threshold: float | None,
    ) -> RagContext: ...


class RagContextProvider:
    def __init__(
        self,
        repository: KnowledgeRepository,
        embedding: EmbeddingPort,
        retriever: RetrieverPort,
        assembler: ContextAssembler,
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._embedding = embedding
        self._retriever = retriever
        self._assembler = assembler
        self._settings = settings

    async def validate_knowledge_base(self, user_id: UUID, knowledge_base_id: UUID) -> None:
        if await self._repository.get_base_for_user(knowledge_base_id, user_id) is None:
            raise KnowledgeBaseNotFoundError("Knowledge base not found")

    async def build(
        self,
        *,
        user_id: UUID,
        knowledge_base_id: UUID,
        query: str,
        top_k: int | None,
        similarity_threshold: float | None,
    ) -> RagContext:
        await self.validate_knowledge_base(user_id, knowledge_base_id)
        bounded_top_k = self._settings.rag_top_k if top_k is None else min(
            max(top_k, 1), self._settings.rag_max_top_k
        )
        threshold = (
            self._settings.rag_similarity_threshold
            if similarity_threshold is None
            else similarity_threshold
        )
        query_vector = await self._embedding.embed_query(query)
        if len(query_vector) != self._settings.embedding_dimensions:
            raise EmbeddingDimensionError("Query embedding dimensions are invalid")
        chunks = await self._retriever.retrieve(
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            query_vector=query_vector,
            top_k=bounded_top_k,
            similarity_threshold=threshold,
        )
        assembled: AssembledContext = self._assembler.assemble(chunks)
        if not assembled.citations and self._settings.rag_no_result_policy == "error":
            raise RagNoResultsError("No relevant knowledge was found")
        return RagContext(prompt=assembled.prompt, citations=assembled.citations)


class NoopContextProvider:
    async def validate_knowledge_base(self, _user_id: UUID, _knowledge_base_id: UUID) -> None:
        return None

    async def build(
        self,
        *,
        user_id: UUID,
        knowledge_base_id: UUID,
        query: str,
        top_k: int | None,
        similarity_threshold: float | None,
    ) -> RagContext:
        del user_id, knowledge_base_id, query, top_k, similarity_threshold
        return RagContext(prompt="", citations=())
