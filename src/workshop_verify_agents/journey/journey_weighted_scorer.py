"""Journey-aware scoring for deterministic workshop demonstrations.

This module compares conventional turn-level averaging against a stage-weighted
method where business-critical stages contribute more strongly to final score.
"""

from __future__ import annotations

from dataclasses import dataclass

from workshop_verify_agents.journey.journey_taxonomy import JourneyStage, coerce_stage, stage_weight


@dataclass(frozen=True)
class BaselineResult:
  """Comparable result for an outcome baseline calculation."""

  method: str
  score: float | None
  rating: str
  thresholds: dict[str, float]
  stages_included: list[str]
  turn_ids_included: list[str]
  explanation: str
  provenance: list[str]


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


def _baseline_rating(score: float, pass_threshold: float, warning_threshold: float) -> str:
  if score >= pass_threshold:
    return "PASS"
  if score >= warning_threshold:
    return "WARNING"
  return "FAIL"


def _baseline_context(
  method: str,
  score: float | None,
  rating: str,
  turn_scores: list[float],
  journey_stages: list[JourneyStage | str],
  turn_ids: list[str] | None,
  thresholds: dict[str, float],
  explanation: str,
) -> BaselineResult:
  if len(turn_scores) != len(journey_stages):
    raise ValueError("turn_scores and journey_stages must have the same length")
  resolved_ids = turn_ids or [str(index) for index in range(len(turn_scores))]
  if len(resolved_ids) != len(turn_scores):
    raise ValueError("turn_ids must have the same length as turn_scores")
  return BaselineResult(
    method=method,
    score=score,
    rating=rating,
    thresholds=thresholds,
    stages_included=[coerce_stage(stage).value for stage in journey_stages],
    turn_ids_included=list(resolved_ids),
    explanation=explanation,
    provenance=[f"turn:{turn_id}" for turn_id in resolved_ids],
  )


def minimum_turn_baseline(
  turn_scores: list[float],
  journey_stages: list[JourneyStage | str],
  turn_ids: list[str] | None = None,
  pass_threshold: float = 0.75,
  warning_threshold: float = 0.60,
) -> BaselineResult:
  """Rate a conversation by its lowest supplied turn score."""
  score = min(turn_scores) if turn_scores else None
  rating = "NOT_APPLICABLE" if score is None else _baseline_rating(
    score, pass_threshold, warning_threshold,
  )
  return _baseline_context(
    "minimum_turn", None if score is None else round(score, 4), rating,
    turn_scores, journey_stages, turn_ids,
    {"pass": pass_threshold, "warning": warning_threshold},
    "The rating is determined by the lowest supplied turn score.",
  )


def critical_stage_only_baseline(
  turn_scores: list[float],
  journey_stages: list[JourneyStage | str],
  turn_ids: list[str] | None = None,
  pass_threshold: float = 0.75,
  warning_threshold: float = 0.60,
) -> BaselineResult:
  """Rate using only turns in configured critical journey stages."""
  critical = {
    JourneyStage.eligibility_or_suitability,
    JourneyStage.recommendation_or_guidance,
  }
  if len(turn_scores) != len(journey_stages):
    raise ValueError("turn_scores and journey_stages must have the same length")
  critical_indexes = [
    index for index, stage_value in enumerate(journey_stages)
    if coerce_stage(stage_value) in critical
  ]
  selected_scores = [turn_scores[index] for index in critical_indexes]
  selected_stages = [journey_stages[index] for index in critical_indexes]
  selected_ids = None if turn_ids is None else [turn_ids[index] for index in critical_indexes]
  if not selected_scores:
    return _baseline_context(
      "critical_stage_only", None, "NOT_APPLICABLE", [], [], [],
      {"pass": pass_threshold, "warning": warning_threshold},
      "Not applicable because no configured critical-stage turns are present.",
    )
  score = round(simple_average_score(selected_scores), 4)
  return _baseline_context(
    "critical_stage_only", score,
    _baseline_rating(score, pass_threshold, warning_threshold),
    selected_scores, selected_stages, selected_ids,
    {"pass": pass_threshold, "warning": warning_threshold},
    "The rating uses the arithmetic mean of configured critical-stage turns.",
  )


def critical_stage_gate_baseline(
  turn_scores: list[float],
  journey_stages: list[JourneyStage | str],
  turn_ids: list[str] | None = None,
  pass_threshold: float = 0.75,
  warning_threshold: float = 0.60,
  critical_warning_threshold: float = 0.75,
  critical_fail_threshold: float = 0.55,
) -> BaselineResult:
  """Apply critical-stage gates before falling back to the flat-mean rating."""
  if critical_fail_threshold > critical_warning_threshold:
    raise ValueError("critical_fail_threshold must not exceed critical_warning_threshold")
  critical = {
    JourneyStage.eligibility_or_suitability,
    JourneyStage.recommendation_or_guidance,
  }
  if len(turn_scores) != len(journey_stages):
    raise ValueError("turn_scores and journey_stages must have the same length")
  critical_indexes = [
    index for index, stage_value in enumerate(journey_stages)
    if coerce_stage(stage_value) in critical
  ]
  critical_scores = [turn_scores[index] for index in critical_indexes]
  flat_score = simple_average_score(turn_scores) if turn_scores else None
  rating = "NOT_APPLICABLE" if flat_score is None else _baseline_rating(
    flat_score, pass_threshold, warning_threshold,
  )
  if critical_scores and min(critical_scores) < critical_fail_threshold:
    rating = "FAIL"
    explanation = "A critical-stage score breached the configured FAIL gate."
  elif critical_scores and min(critical_scores) < critical_warning_threshold:
    rating = "WARNING"
    explanation = "A critical-stage score breached the configured WARNING gate."
  else:
    explanation = "No critical-stage gate was breached; the flat-mean rating was used."
  return _baseline_context(
    "critical_stage_gate", flat_score, rating,
    turn_scores, journey_stages, turn_ids,
    {
      "pass": pass_threshold,
      "warning": warning_threshold,
      "critical_warning": critical_warning_threshold,
      "critical_fail": critical_fail_threshold,
    },
    explanation,
  )


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
