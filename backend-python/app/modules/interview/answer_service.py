from collections.abc import Sequence
from typing import cast
from uuid import UUID

from app.ai.evaluation import InterviewAnswerEvaluatorPort
from app.ai.followup import FollowUpQuestionGeneratorPort
from app.core.config import Settings
from app.modules.interview.answer_workflow import InterviewAnswerWorkflow
from app.modules.interview.context import InterviewEvaluationContextProviderPort
from app.modules.interview.domain import InterviewProgress, InterviewStatus
from app.modules.interview.exceptions import (
    InterviewAnswerConflictError,
    InterviewAnswerError,
    InterviewEvaluationQueueUnavailableError,
    InterviewNotFoundError,
    InvalidInterviewTransitionError,
)
from app.modules.interview.follow_up import FollowUpPolicy
from app.modules.interview.repository import InterviewRepository
from app.workers.queue import (
    InterviewAnswerEvaluationJob,
    InterviewAnswerEvaluationTaskQueuePort,
    TaskQueuePort,
)


class InterviewAnswerService:
    def __init__(
        self,
        repository: InterviewRepository,
        context_provider: InterviewEvaluationContextProviderPort,
        evaluator: InterviewAnswerEvaluatorPort,
        follow_up_generator: FollowUpQuestionGeneratorPort,
        task_queue: InterviewAnswerEvaluationTaskQueuePort | TaskQueuePort,
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._task_queue = task_queue
        self._settings = settings
        policy = FollowUpPolicy(
            max_depth=settings.interview_max_follow_up_depth,
            score_threshold=settings.interview_follow_up_score_threshold,
            max_follow_ups_per_session=settings.interview_max_follow_ups_per_session,
            min_answer_length=settings.interview_min_answer_length,
            max_answer_length=settings.interview_max_answer_length,
        )
        self._workflow = InterviewAnswerWorkflow(
            repository,
            context_provider,
            evaluator,
            follow_up_generator,
            policy,
        )

    async def submit_answer(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        turn_id: UUID,
        answer: str,
        request_id: str,
    ) -> InterviewProgress:
        content = answer.strip()
        if len(content) < self._settings.interview_min_answer_length:
            raise InterviewAnswerError("Answer is too short")
        if len(content) > self._settings.interview_max_answer_length:
            raise InterviewAnswerError("Answer is too long")
        clean_request_id = request_id.strip()
        if not clean_request_id or len(clean_request_id) > 128:
            raise InterviewAnswerError("requestId is invalid")
        session = await self._repository.get_for_user(session_id, user_id)
        if session is None:
            raise InterviewNotFoundError("Interview session not found")
        if session.status != InterviewStatus.IN_PROGRESS:
            raise InvalidInterviewTransitionError("Interview is not in progress")
        existing = await self._repository.find_answer_by_request(
            session_id, user_id, clean_request_id
        )
        if existing is not None:
            if (
                existing.turn.status.value == "EVALUATING"
                and existing.evaluation is None
                and existing.turn.evaluation_failure_code
                == "INTERVIEW_EVALUATION_QUEUE_UNAVAILABLE"
            ):
                await self._enqueue_evaluation(existing, user_id, session_id, clean_request_id)
            return existing
        try:
            progress = await self._repository.submit_answer(
                session_id,
                turn_id,
                user_id,
                content,
                clean_request_id,
            )
        except InvalidInterviewTransitionError as exc:
            raise InterviewAnswerConflictError(exc.message) from exc
        if callable(getattr(self._task_queue, "enqueue_interview_answer_evaluation", None)):
            await self._enqueue_evaluation(progress, user_id, session_id, clean_request_id)
        else:
            async def evaluate_task() -> None:
                await self._workflow.evaluate(user_id, session_id, turn_id, content)

            try:
                await cast(TaskQueuePort, self._task_queue).enqueue(evaluate_task)
            except Exception:
                await self._repository.fail_evaluation(
                    session_id,
                    turn_id,
                    user_id,
                    "INTERVIEW_EVALUATION_QUEUE_FAILED",
                    "Interview evaluation could not be queued",
                )
        return progress

    async def _enqueue_evaluation(
        self,
        progress: InterviewProgress,
        user_id: UUID,
        session_id: UUID,
        request_id: str,
    ) -> None:
        enqueue = cast(
            InterviewAnswerEvaluationTaskQueuePort, self._task_queue
        ).enqueue_interview_answer_evaluation
        if progress.answer is None:
            raise InterviewEvaluationQueueUnavailableError(
                "Interview evaluation is temporarily unavailable"
            )
        try:
            await enqueue(
                InterviewAnswerEvaluationJob(
                    user_id=user_id,
                    session_id=session_id,
                    turn_id=progress.turn.id,
                    answer_id=progress.answer.id,
                    request_id=request_id,
                )
            )
        except Exception as exc:
            marker = getattr(self._repository, "mark_evaluation_queue_unavailable", None)
            if callable(marker):
                try:
                    await marker(
                        session_id,
                        progress.turn.id,
                        user_id,
                        "INTERVIEW_EVALUATION_QUEUE_UNAVAILABLE",
                        "Interview evaluation is waiting to be rescheduled",
                    )
                except Exception as marker_exc:
                    raise InterviewEvaluationQueueUnavailableError(
                        "Interview evaluation is temporarily unavailable"
                    ) from marker_exc
            raise InterviewEvaluationQueueUnavailableError(
                "Interview evaluation is temporarily unavailable"
            ) from exc

    async def current_turn(self, user_id: UUID, session_id: UUID) -> InterviewProgress:
        session = await self._repository.get_for_user(session_id, user_id)
        if session is None:
            raise InterviewNotFoundError("Interview session not found")
        turn = await self._repository.get_current_turn(session_id, user_id)
        if turn is None:
            raise InterviewNotFoundError("Current interview turn not found")
        return InterviewProgress(
            session=session,
            turn=turn,
            answer=await self._repository.get_answer_for_turn(turn.id, user_id),
            evaluation=await self._repository.get_evaluation_for_turn(turn.id, user_id),
        )

    async def list_turns(self, user_id: UUID, session_id: UUID) -> Sequence[InterviewProgress]:
        session = await self._repository.get_for_user(session_id, user_id)
        if session is None:
            raise InterviewNotFoundError("Interview session not found")
        progress: list[InterviewProgress] = []
        for turn in await self._repository.list_turns(session_id, user_id):
            progress.append(
                InterviewProgress(
                    session=session,
                    turn=turn,
                    answer=await self._repository.get_answer_for_turn(turn.id, user_id),
                    evaluation=await self._repository.get_evaluation_for_turn(turn.id, user_id),
                )
            )
        return progress

    async def get_turn(
        self, user_id: UUID, turn_id: UUID, session_id: UUID | None = None
    ) -> InterviewProgress:
        turn = await self._repository.get_turn_for_user(turn_id, user_id)
        if turn is None:
            raise InterviewNotFoundError("Interview turn not found")
        if session_id is not None and turn.session_id != session_id:
            raise InterviewNotFoundError("Interview turn not found")
        session = await self._repository.get_for_user(turn.session_id, user_id)
        if session is None:
            raise InterviewNotFoundError("Interview session not found")
        return InterviewProgress(
            session=session,
            turn=turn,
            answer=await self._repository.get_answer_for_turn(turn.id, user_id),
            evaluation=await self._repository.get_evaluation_for_turn(turn.id, user_id),
        )
