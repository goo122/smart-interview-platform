from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.modules.interview.domain import InterviewEvaluation, InterviewTurn, TurnType


@dataclass(frozen=True, slots=True)
class ReportAggregationWeights:
    primary_turn: float = 1.0
    follow_up_turn: float = 0.5
    technical: float = 0.35
    relevance: float = 0.20
    clarity: float = 0.20
    depth: float = 0.25


@dataclass(frozen=True, slots=True)
class AggregatedReportScores:
    overall_score: int
    technical_score: int
    relevance_score: int
    clarity_score: int
    depth_score: int
    radar_data: tuple[dict[str, int | str], ...]


class InterviewScoreAggregator:
    """Deterministically aggregate completed turn evaluations into report scores."""

    def __init__(self, weights: ReportAggregationWeights | None = None) -> None:
        self.weights = weights or ReportAggregationWeights()
        values = (
            self.weights.primary_turn,
            self.weights.follow_up_turn,
            self.weights.technical,
            self.weights.relevance,
            self.weights.clarity,
            self.weights.depth,
        )
        if any(value < 0 for value in values):
            raise ValueError("report weights must be non-negative")
        if abs(
            self.weights.technical
            + self.weights.relevance
            + self.weights.clarity
            + self.weights.depth
            - 1.0
        ) > 1e-6:
            raise ValueError("report dimension weights must sum to 1")
        if self.weights.primary_turn == 0 and self.weights.follow_up_turn == 0:
            raise ValueError("at least one report turn weight must be positive")

    def aggregate(
        self, snapshots: Iterable[tuple[InterviewTurn, InterviewEvaluation]]
    ) -> AggregatedReportScores:
        values = list(snapshots)
        if not values:
            raise ValueError("at least one completed evaluation is required")
        total_weight = 0.0
        dimensions = {
            "technical": 0.0,
            "relevance": 0.0,
            "clarity": 0.0,
            "depth": 0.0,
        }
        for turn, evaluation in values:
            weight = (
                self.weights.primary_turn
                if turn.turn_type == TurnType.PRIMARY
                else self.weights.follow_up_turn
            )
            if weight <= 0:
                continue
            total_weight += weight
            dimensions["technical"] += evaluation.technical_score * weight
            dimensions["relevance"] += evaluation.relevance_score * weight
            dimensions["clarity"] += evaluation.clarity_score * weight
            dimensions["depth"] += evaluation.depth_score * weight
        if total_weight <= 0:
            raise ValueError("no evaluations have a positive turn weight")
        normalized = {
            name: _round_score(value / total_weight) for name, value in dimensions.items()
        }
        overall = _round_score(
            normalized["technical"] * self.weights.technical
            + normalized["relevance"] * self.weights.relevance
            + normalized["clarity"] * self.weights.clarity
            + normalized["depth"] * self.weights.depth
        )
        radar: tuple[dict[str, int | str], ...] = tuple(
            {"dimension": name, "score": normalized[name]}
            for name in ("technical", "relevance", "clarity", "depth")
        )
        return AggregatedReportScores(
            overall_score=overall,
            technical_score=normalized["technical"],
            relevance_score=normalized["relevance"],
            clarity_score=normalized["clarity"],
            depth_score=normalized["depth"],
            radar_data=radar,
        )


def _round_score(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
