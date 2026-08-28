from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embedding import EmbeddingPort
from app.ai.evaluation import InterviewAnswerEvaluatorPort, UnavailableInterviewAnswerEvaluator
from app.ai.followup import FollowUpQuestionGeneratorPort, UnavailableFollowUpQuestionGenerator
from app.ai.interview import (
    InterviewQuestionGeneratorPort,
    UnavailableInterviewQuestionGenerator,
)
from app.core.config import Settings, get_settings
from app.infrastructure.vectorstore.retriever import PgVectorRetriever
from app.modules.auth.dependencies import get_db_session
from app.modules.interview.answer_service import InterviewAnswerService
from app.modules.interview.context import (
    InterviewContextProvider,
    InterviewContextProviderPort,
    InterviewEvaluationContextProvider,
    InterviewEvaluationContextProviderPort,
)
from app.modules.interview.repository import (
    InterviewRepository,
    SqlAlchemyInterviewRepository,
)
from app.modules.interview.service import InterviewService
from app.modules.knowledge.context import ContextAssembler
from app.modules.knowledge.dependencies import (
    get_embedding,
    get_knowledge_repository,
    get_task_queue,
)
from app.modules.knowledge.repository import KnowledgeRepository
from app.modules.knowledge.retrieval import RetrieverPort
from app.workers.queue import TaskQueuePort


async def get_interview_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InterviewRepository:
    return SqlAlchemyInterviewRepository(session)


async def get_interview_retriever(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RetrieverPort:
    return PgVectorRetriever(session, settings.embedding_dimensions)


def get_interview_context_provider(
    repository: Annotated[KnowledgeRepository, Depends(get_knowledge_repository)],
    embedding: Annotated[EmbeddingPort, Depends(get_embedding)],
    retriever: Annotated[RetrieverPort, Depends(get_interview_retriever)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> InterviewContextProviderPort:
    return InterviewContextProvider(
        repository,
        embedding,
        retriever,
        ContextAssembler(settings.rag_max_context_tokens, settings.rag_max_chunk_tokens),
        settings,
    )


def get_interview_question_generator(request: Request) -> InterviewQuestionGeneratorPort:
    return cast(
        InterviewQuestionGeneratorPort,
        getattr(
            request.app.state,
            "interview_question_generator",
            UnavailableInterviewQuestionGenerator(),
        ),
    )


def get_interview_answer_evaluator(request: Request) -> InterviewAnswerEvaluatorPort:
    return cast(
        InterviewAnswerEvaluatorPort,
        getattr(
            request.app.state,
            "interview_answer_evaluator",
            UnavailableInterviewAnswerEvaluator(),
        ),
    )


def get_follow_up_question_generator(request: Request) -> FollowUpQuestionGeneratorPort:
    return cast(
        FollowUpQuestionGeneratorPort,
        getattr(
            request.app.state,
            "follow_up_question_generator",
            UnavailableFollowUpQuestionGenerator(),
        ),
    )


def get_interview_evaluation_context_provider(
    repository: Annotated[KnowledgeRepository, Depends(get_knowledge_repository)],
    embedding: Annotated[EmbeddingPort, Depends(get_embedding)],
    retriever: Annotated[RetrieverPort, Depends(get_interview_retriever)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> InterviewEvaluationContextProviderPort:
    return InterviewEvaluationContextProvider(
        repository,
        embedding,
        retriever,
        ContextAssembler(settings.rag_max_context_tokens, settings.rag_max_chunk_tokens),
        settings,
    )


def get_interview_service(
    repository: Annotated[InterviewRepository, Depends(get_interview_repository)],
    context_provider: Annotated[
        InterviewContextProviderPort, Depends(get_interview_context_provider)
    ],
    generator: Annotated[
        InterviewQuestionGeneratorPort, Depends(get_interview_question_generator)
    ],
    task_queue: Annotated[TaskQueuePort, Depends(get_task_queue)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> InterviewService:
    return InterviewService(repository, context_provider, generator, task_queue, settings)


def get_interview_answer_service(
    repository: Annotated[InterviewRepository, Depends(get_interview_repository)],
    context_provider: Annotated[
        InterviewEvaluationContextProviderPort,
        Depends(get_interview_evaluation_context_provider),
    ],
    evaluator: Annotated[
        InterviewAnswerEvaluatorPort, Depends(get_interview_answer_evaluator)
    ],
    follow_up_generator: Annotated[
        FollowUpQuestionGeneratorPort, Depends(get_follow_up_question_generator)
    ],
    task_queue: Annotated[TaskQueuePort, Depends(get_task_queue)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> InterviewAnswerService:
    return InterviewAnswerService(
        repository,
        context_provider,
        evaluator,
        follow_up_generator,
        task_queue,
        settings,
    )
