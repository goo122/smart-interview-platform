from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.ai.embedding import EmbeddingPort
from app.core.config import Settings
from app.modules.interview.exceptions import InterviewKnowledgeUnavailableError
from app.modules.knowledge.context import ContextAssembler, ContextCitation
from app.modules.knowledge.exceptions import EmbeddingDimensionError, KnowledgeBaseNotFoundError
from app.modules.knowledge.repository import KnowledgeRepository
from app.modules.knowledge.retrieval import RetrieverPort


@dataclass(frozen=True, slots=True)
class InterviewContext:
    prompt: str
    citations: tuple[ContextCitation, ...]


class InterviewContextProviderPort(Protocol):
    async def validate_knowledge_base(self, user_id: UUID, knowledge_base_id: UUID) -> None: ...

    async def build(
        self,
        *,
        user_id: UUID,
        knowledge_base_id: UUID,
        job_title: str,
        job_description: str,
        difficulty: str,
        question_count: int,
    ) -> InterviewContext: ...


class InterviewContextProvider:
    """Build bounded, user-scoped resume context for interview preparation."""

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
        job_title: str,
        job_description: str,
        difficulty: str,
        question_count: int,
    ) -> InterviewContext:
        await self.validate_knowledge_base(user_id, knowledge_base_id)
        query = (
            f"岗位：{job_title}\n岗位描述：{job_description}\n"
            f"难度：{difficulty}\n题目数：{question_count}"
        )
        query_vector = await self._embedding.embed_query(query)
        if len(query_vector) != self._settings.embedding_dimensions:
            raise EmbeddingDimensionError("Query embedding dimensions are invalid")
        chunks = await self._retriever.retrieve(
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            query_vector=query_vector,
            top_k=self._settings.rag_top_k,
            similarity_threshold=self._settings.rag_similarity_threshold,
        )
        assembled = self._assembler.assemble(chunks)
        if not assembled.citations:
            raise InterviewKnowledgeUnavailableError("No ready resume content was found")
        return InterviewContext(prompt=assembled.prompt, citations=assembled.citations)
