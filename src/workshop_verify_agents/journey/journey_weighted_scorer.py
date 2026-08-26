"""Journey-aware scoring for deterministic workshop demonstrations.

This module compares conventional turn-level averaging against a stage-weighted
method where business-critical stages contribute more strongly to final score.
"""

from __future__ import annotations

from dataclasses import dataclass

from workshop_verify_agents.journey.journey_taxonomy import JourneyStage, coerce_stage, stage_weight


@dataclass(frozen=True)
class StageScoreBreakdown:
  """Contribution of a single turn to the weighted aggregate."""

  turn_index: int
  stage: JourneyStage
  score: float
  weight: float
  weighted_contribution: float


def simple_average_score(turn_scores: list[float]) -> float:
  """Return unweighted arithmetic mean of turn scores."""
  if not turn_scores:
    return 0.0
  return round(sum(turn_scores) / len(turn_scores), 4)


def journey_weighted_score(
  turn_scores: list[float],
  journey_stages: list[JourneyStage | str],
) -> tuple[float, list[StageScoreBreakdown]]:
  """Return stage-weighted score and per-turn weighted contributions."""
  if len(turn_scores) != len(journey_stages):
    raise ValueError("turn_scores and journey_stages must have the same length")
  if not turn_scores:
    return 0.0, []

  numerator = 0.0
  denominator = 0.0
  breakdown: list[StageScoreBreakdown] = []

  for idx, (score, stage_value) in enumerate(zip(turn_scores, journey_stages)):
    stage = coerce_stage(stage_value)
    weight = stage_weight(stage)
    contribution = score * weight
    numerator += contribution
    denominator += weight
    breakdown.append(StageScoreBreakdown(
      turn_index=idx,
      stage=stage,
      score=score,
      weight=weight,
      weighted_contribution=round(contribution, 4),
    ))

  weighted = numerator / denominator if denominator > 0 else 0.0
  return round(weighted, 4), breakdown


def _rating(score: float) -> str:
  """Deterministic three-level rating used in notebook demonstrations."""
  if score >= 0.75:
    return "PASS"
  if score >= 0.60:
    return "WARNING"
  return "FAIL"


def _critical_stage_failures(
  turn_scores: list[float],
  journey_stages: list[JourneyStage | str],
) -> list[dict[str, str | int | float]]:
  """Return low-scoring failures in high-impact compliance stages."""
  critical = {
    JourneyStage.eligibility_or_suitability,
    JourneyStage.recommendation_or_guidance,
  }
  threshold = 0.55
  failures: list[dict[str, str | int | float]] = []

  for idx, (score, stage_value) in enumerate(zip(turn_scores, journey_stages)):
    stage = coerce_stage(stage_value)
    if stage in critical and score < threshold:
      failures.append({
        "turn_index": idx,
        "stage": stage.value,
        "score": round(score, 4),
        "threshold": threshold,
        "reason": "Low score in business-critical stage.",
      })
  return failures


def compare_scoring_methods(
  turn_scores: list[float],
  journey_stages: list[JourneyStage | str],
) -> dict[str, object]:
  """Compare simple and journey-aware methods for the same conversation."""
  average = simple_average_score(turn_scores)
  weighted, breakdown = journey_weighted_score(turn_scores, journey_stages)
  delta = round(weighted - average, 4)
  critical_failures = _critical_stage_failures(turn_scores, journey_stages)

  simple_rating = _rating(average)
  weighted_rating = _rating(weighted)

  if critical_failures and weighted_rating == "PASS":
    weighted_rating = "WARNING"

  explanation = (
    "Journey-aware weighting reduced the score because low-performing turns "
    "occurred in high-importance stages."
    if weighted < average else
    "Journey-aware weighting did not penalize the conversation relative to simple averaging."
  )

  return {
    "simple_average": average,
    "journey_weighted_score": weighted,
    "score_delta": delta,
    "simple_rating": simple_rating,
    "journey_weighted_rating": weighted_rating,
    "critical_stage_failures": critical_failures,
    "breakdown": [
      {
        "turn_index": item.turn_index,
        "stage": item.stage.value,
        "score": item.score,
        "weight": item.weight,
        "weighted_contribution": item.weighted_contribution,
      }
      for item in breakdown
    ],
    "explanation": explanation,
  }


def compare_conversation(conversation: dict[str, object]) -> dict[str, object]:
  """Notebook helper using the example conversation object shape."""
  exchanges = list(conversation.get("exchanges", []))
  if exchanges:
    turn_scores = [float(exchange["quality_score"]) for exchange in exchanges]
    stages = [str(exchange["journey_stage"]) for exchange in exchanges]
  else:
    turn_scores = list(conversation.get("mocked_quality_scores", []))
    stages = list(conversation.get("expected_stage_labels", []))
  result = compare_scoring_methods(turn_scores=turn_scores, journey_stages=stages)
  return {
    "scenario_name": conversation.get("scenario_name", "unknown"),
    **result,
  }
