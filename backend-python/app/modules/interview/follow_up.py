from dataclasses import dataclass

from app.ai.evaluation import StructuredInterviewEvaluation
from app.modules.interview.domain import FollowUpDecision


@dataclass(frozen=True, slots=True)
class FollowUpPolicy:
    max_depth: int
    score_threshold: int
    max_follow_ups_per_session: int
    min_answer_length: int
    max_answer_length: int = 10000

    def __post_init__(self) -> None:
        if self.max_depth < 0:
            raise ValueError("max_depth must be non-negative")
        if not 0 <= self.score_threshold <= 100:
            raise ValueError("score_threshold must be between 0 and 100")
        if self.max_follow_ups_per_session < 0:
            raise ValueError("max_follow_ups_per_session must be non-negative")
        if self.min_answer_length < 1:
            raise ValueError("min_answer_length must be positive")
        if self.max_answer_length < self.min_answer_length:
            raise ValueError("max_answer_length must not be smaller than min_answer_length")

    def decide(
        self,
        evaluation: StructuredInterviewEvaluation,
        *,
        follow_up_depth: int,
        follow_up_count: int,
        answer_length: int,
        has_next_question: bool = True,
    ) -> FollowUpDecision:
        if not evaluation.should_follow_up:
            return FollowUpDecision(False, "llm_did_not_recommend_follow_up")
        if follow_up_depth >= self.max_depth:
            return FollowUpDecision(False, "max_follow_up_depth_reached")
        if follow_up_count >= self.max_follow_ups_per_session:
            return FollowUpDecision(False, "max_session_follow_ups_reached")
        if answer_length <= 0 or answer_length > self.max_answer_length:
            return FollowUpDecision(False, "answer_length_out_of_range")
        if answer_length < self.min_answer_length:
            return FollowUpDecision(True, "answer_needs_clarification")
        if (
            evaluation.overall_score >= self.score_threshold
            and evaluation.technical_score >= self.score_threshold
        ):
            return FollowUpDecision(False, "score_above_follow_up_threshold")
        if not has_next_question:
            return FollowUpDecision(True, "final_question_needs_clarification")
        return FollowUpDecision(True, "score_below_follow_up_threshold")
