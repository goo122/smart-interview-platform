from app.modules.interview.domain import InterviewStatus, TurnStatus
from app.modules.interview.exceptions import InvalidInterviewTransitionError


class InterviewStateMachine:
    """Single source of truth for interview lifecycle transitions."""

    _allowed: dict[InterviewStatus, frozenset[InterviewStatus]] = {
        InterviewStatus.CREATED: frozenset(
            {InterviewStatus.PREPARING, InterviewStatus.CANCELLED}
        ),
        InterviewStatus.PREPARING: frozenset(
            {InterviewStatus.READY, InterviewStatus.FAILED, InterviewStatus.CANCELLED}
        ),
        InterviewStatus.READY: frozenset(
            {InterviewStatus.IN_PROGRESS, InterviewStatus.CANCELLED}
        ),
        InterviewStatus.IN_PROGRESS: frozenset(
            {InterviewStatus.COMPLETED, InterviewStatus.FAILED}
        ),
        InterviewStatus.COMPLETED: frozenset(),
        InterviewStatus.FAILED: frozenset(),
        InterviewStatus.CANCELLED: frozenset(),
    }

    _allowed_turn: dict[TurnStatus, frozenset[TurnStatus]] = {
        TurnStatus.WAITING_ANSWER: frozenset({TurnStatus.EVALUATING, TurnStatus.SKIPPED}),
        TurnStatus.EVALUATING: frozenset(
            {TurnStatus.COMPLETED, TurnStatus.FAILED, TurnStatus.SKIPPED}
        ),
        TurnStatus.COMPLETED: frozenset(),
        TurnStatus.FAILED: frozenset(),
        TurnStatus.SKIPPED: frozenset(),
    }

    def transition(self, current: InterviewStatus, target: InterviewStatus) -> None:
        if target not in self._allowed.get(current, frozenset()):
            raise InvalidInterviewTransitionError(
                f"Cannot transition interview from {current.value} to {target.value}"
            )

    def can_cancel(self, current: InterviewStatus) -> bool:
        return InterviewStatus.CANCELLED in self._allowed.get(current, frozenset())

    def can_start(self, current: InterviewStatus) -> bool:
        return current == InterviewStatus.READY

    def transition_turn(self, current: TurnStatus, target: TurnStatus) -> None:
        if target not in self._allowed_turn.get(current, frozenset()):
            raise InvalidInterviewTransitionError(
                f"Cannot transition interview turn from {current.value} to {target.value}"
            )

    def can_answer(self, current: TurnStatus) -> bool:
        return current == TurnStatus.WAITING_ANSWER
