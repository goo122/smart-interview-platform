from collections.abc import Sequence
from typing import cast
from uuid import UUID

from app.ai.interview import InterviewQuestionGeneratorPort
from app.ai.resume import (
    ResumeEvaluatorPort,
    ResumeRoleInferencePort,
    ResumeRoleInferenceRequest,
    StructuredResumeRoleInference,
)
from app.core.config import Settings
from app.modules.interview.context import InterviewContextProviderPort
from app.modules.interview.domain import (
    InterviewDifficulty,
    InterviewEvent,
    InterviewQuestion,
    InterviewSession,
    InterviewStatus,
    InterviewType,
    ResumeEvaluation,
)
from app.modules.interview.exceptions import (
    InterviewNotFoundError,
    InterviewRequestAlreadyExistsError,
    InvalidInterviewRequestError,
    InvalidInterviewTransitionError,
)
from app.modules.interview.repository import InterviewRepository
from app.modules.interview.workflow import InterviewPreparationWorkflow
from app.workers.queue import TaskQueuePort

CONVERSATION_STATUS_TO_DOMAIN: dict[str, InterviewStatus] = {
    "CREATED": InterviewStatus.CREATED,
    "DRAFT": InterviewStatus.CREATED,
    "PREPARING": InterviewStatus.PREPARING,
    "RESUME_UPLOADING": InterviewStatus.PREPARING,
    "READY": InterviewStatus.READY,
    "IN_PROGRESS": InterviewStatus.IN_PROGRESS,
    "COMPLETED": InterviewStatus.COMPLETED,
    "FAILED": InterviewStatus.FAILED,
    "CANCELLED": InterviewStatus.CANCELLED,
}


class InterviewService:
    def __init__(
        self,
        repository: InterviewRepository,
        context_provider: InterviewContextProviderPort,
        generator: InterviewQuestionGeneratorPort,
        task_queue: TaskQueuePort,
        settings: Settings,
        resume_evaluator: ResumeEvaluatorPort | None = None,
        role_inference: ResumeRoleInferencePort | None = None,
    ) -> None:
        self._repository = repository
        self._context_provider = context_provider
        self._generator = generator
        self._task_queue = task_queue
        self._settings = settings
        self._workflow = InterviewPreparationWorkflow(
            repository, context_provider, generator, resume_evaluator
        )
        self._role_inference = role_inference

    async def infer_resume_role(
        self, user_id: UUID, knowledge_base_id: UUID
    ) -> StructuredResumeRoleInference:
        """Infer a role from the user's ready resume context only."""

        await self._context_provider.validate_knowledge_base(user_id, knowledge_base_id)
        context = await self._context_provider.build(
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            job_title="简历岗位方向分析",
            job_description="根据简历中的教育、工作经历、项目、技能和成果识别最匹配的岗位方向。",
            difficulty="MEDIUM",
            question_count=5,
        )
        if self._role_inference is None:
            raise RuntimeError("No resume role inference is configured")
        return await self._role_inference.infer(
            ResumeRoleInferenceRequest(
                resume_context=context.prompt,
                source_ids=tuple(citation.source_id for citation in context.citations),
            )
        )

    async def create_session(
        self,
        *,
        user_id: UUID,
        knowledge_base_id: UUID,
        job_title: str,
        job_description: str,
        interview_type: InterviewType,
        difficulty: InterviewDifficulty,
        question_count: int,
        request_id: str | None,
    ) -> InterviewSession:
        clean_title = job_title.strip()
        clean_description = job_description.strip()
        if not clean_title or not clean_description:
            raise InvalidInterviewRequestError("Job title and description are required")
        if not 3 <= question_count <= 20:
            raise InvalidInterviewRequestError("questionCount must be between 3 and 20")
        clean_request_id = request_id.strip() if request_id else None
        if clean_request_id == "":
            clean_request_id = None
        if clean_request_id and len(clean_request_id) > 128:
            raise InvalidInterviewRequestError("requestId is too long")
        await self._context_provider.validate_knowledge_base(user_id, knowledge_base_id)
        if clean_request_id:
            existing = await self._repository.find_by_request(user_id, clean_request_id)
            if existing is not None:
                return existing
        session = InterviewSession.new(
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            job_title=clean_title,
            job_description=clean_description,
            interview_type=interview_type,
            difficulty=difficulty,
            question_count=question_count,
            request_id=clean_request_id,
        )
        try:
            created = await self._repository.create(session)
        except InterviewRequestAlreadyExistsError:
            if not clean_request_id:
                raise
            existing = await self._repository.find_by_request(user_id, clean_request_id)
            if existing is None:
                raise
            return existing
        try:
            async def prepare_task() -> None:
                await self._workflow.prepare(user_id, created.id)

            await self._task_queue.enqueue(prepare_task)
        except Exception:
            await self._repository.mark_failed(
                created.id,
                user_id,
                "INTERVIEW_QUEUE_FAILED",
                "Interview preparation could not be queued",
            )
        result = await self._repository.get_for_user(created.id, user_id)
        if result is None:
            raise InterviewNotFoundError("Interview session not found")
        return result

    async def prepare(self, user_id: UUID, session_id: UUID) -> InterviewSession:
        await self.get_session(user_id, session_id)
        return await self._workflow.prepare(user_id, session_id)

    async def list_sessions(
        self, user_id: UUID, current: int = 1, size: int = 10
    ) -> tuple[list[InterviewSession], int]:
        current = max(current, 1)
        size = min(max(size, 1), 100)
        return await self._repository.list_for_user(user_id, current, size)

    async def list_conversations(
        self,
        user_id: UUID,
        current: int = 1,
        size: int = 10,
        status: str | None = None,
        keyword: str | None = None,
    ) -> tuple[list[InterviewSession], int]:
        current = max(current, 1)
        size = min(max(size, 1), 100)
        normalized_status = status.strip().upper() if status else None
        domain_status = (
            CONVERSATION_STATUS_TO_DOMAIN.get(normalized_status)
            if normalized_status
            else None
        )
        if normalized_status and domain_status is None:
            raise InvalidInterviewRequestError("Unsupported conversation status")
        return await self._repository.list_conversations_for_user(
            user_id,
            current,
            size,
            domain_status,
            keyword.strip() if keyword else None,
        )

    async def get_session(self, user_id: UUID, session_id: UUID) -> InterviewSession:
        result = await self._repository.get_for_user(session_id, user_id)
        if result is None:
            raise InterviewNotFoundError("Interview session not found")
        return result

    async def get_resume_evaluation(
        self, user_id: UUID, session_id: UUID
    ) -> ResumeEvaluation | None:
        await self.get_session(user_id, session_id)
        getter = getattr(self._repository, "get_resume_evaluation", None)
        if getter is None:
            return None
        return cast(ResumeEvaluation | None, await getter(session_id, user_id))

    async def get_questions(self, user_id: UUID, session_id: UUID) -> Sequence[InterviewQuestion]:
        session = await self.get_session(user_id, session_id)
        if session.status not in {
            InterviewStatus.READY,
            InterviewStatus.IN_PROGRESS,
            InterviewStatus.COMPLETED,
        }:
            raise InvalidInterviewRequestError("Interview questions are not ready")
        questions = await self._repository.list_questions(session_id)
        if session.status == InterviewStatus.IN_PROGRESS:
            visible = [
                question
                for question in questions
                if question.sequence == session.current_question_index + 1
            ]
            return visible or questions[:1]
        return questions[:1] if questions else []

    async def get_events(self, user_id: UUID, session_id: UUID) -> Sequence[InterviewEvent]:
        await self.get_session(user_id, session_id)
        return await self._repository.list_events(session_id)

    async def start(self, user_id: UUID, session_id: UUID) -> InterviewSession:
        await self.get_session(user_id, session_id)
        return await self._repository.start(session_id, user_id)

    async def cancel(self, user_id: UUID, session_id: UUID) -> InterviewSession:
        await self.get_session(user_id, session_id)
        return await self._repository.cancel(session_id, user_id)

    async def finish(self, user_id: UUID, session_id: UUID) -> InterviewSession:
        session = await self.get_session(user_id, session_id)
        if session.status == InterviewStatus.COMPLETED:
            return session
        if session.status in {InterviewStatus.CANCELLED, InterviewStatus.FAILED}:
            raise InvalidInterviewTransitionError(
                f"Cannot finish an interview with status {session.status.value}"
            )
        if session.status != InterviewStatus.IN_PROGRESS:
            raise InvalidInterviewTransitionError("Only an in-progress interview can be finished")
        return await self._repository.finish(session_id, user_id)
