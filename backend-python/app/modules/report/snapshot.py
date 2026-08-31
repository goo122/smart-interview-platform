from collections.abc import Iterable, Sequence
from uuid import UUID

from app.modules.interview.domain import (
    InterviewEvaluation,
    InterviewQuestion,
    InterviewSession,
    InterviewTurn,
    TurnStatus,
)
from app.modules.report.domain import ReportTurnSnapshot


class InterviewReportSnapshotBuilder:
    """Validate completed interview data and produce immutable report inputs."""

    def build(
        self,
        session: InterviewSession,
        turns: Sequence[InterviewTurn],
        answers: dict[UUID, str],
        evaluations: dict[UUID, InterviewEvaluation],
        questions: Iterable[InterviewQuestion],
    ) -> tuple[ReportTurnSnapshot, ...]:
        completed_turns = [turn for turn in turns if turn.status == TurnStatus.COMPLETED]
        if not completed_turns:
            raise ValueError("Interview has no completed turns")
        question_map = {question.id: question for question in questions}
        snapshots: list[ReportTurnSnapshot] = []
        for turn in sorted(completed_turns, key=lambda item: item.sequence):
            answer = answers.get(turn.id)
            evaluation = evaluations.get(turn.id)
            if answer is None or evaluation is None:
                continue
            snapshots.append(
                ReportTurnSnapshot(
                    turn=turn,
                    answer=answer,
                    evaluation=evaluation,
                    question=question_map.get(turn.question_id)
                    if turn.question_id is not None
                    else None,
                )
            )
        if not snapshots:
            raise ValueError("Interview has no completed turns with answer and evaluation")
        if session.status.value != "COMPLETED":
            raise ValueError("Only completed interviews can produce reports")
        return tuple(snapshots)
