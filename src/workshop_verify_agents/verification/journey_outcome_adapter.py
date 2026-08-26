"""Adapter from journey-aware scoring output to verification outcome evidence."""

from __future__ import annotations

from workshop_verify_agents.verification.evidence_schema import (
    EvidenceStatus,
    EvidenceType,
    VerificationEvidence,
)


def build_outcome_evidence_from_journey_result(
    conversation_id: str,
    journey_result: dict[str, object],
) -> list[VerificationEvidence]:
    """Map journey-aware scoring output to ``EvidenceType.outcome`` evidence.

    Expected keys in ``journey_result`` are produced by
    ``journey_weighted_scorer.compare_scoring_methods``.
    """
    if not journey_result or not isinstance(journey_result, dict):
        return [VerificationEvidence(
            conversation_id=conversation_id,
            evidence_type=EvidenceType.outcome,
            related_signals=[],
            status=EvidenceStatus.indeterminate,
            explanation=(
                "Journey-aware outcome evidence is indeterminate: "
                "no valid journey result was provided."
            ),
        )]

    simple_average = journey_result.get("simple_average")
    weighted_score = journey_result.get("journey_weighted_score")
    simple_rating = str(journey_result.get("simple_rating", "UNKNOWN")).upper()
    weighted_rating = str(journey_result.get("journey_weighted_rating", "UNKNOWN")).upper()
    critical_failures = journey_result.get("critical_stage_failures", [])

    status = _rating_to_status(weighted_rating)

    if simple_rating and simple_rating != "UNKNOWN" and weighted_rating and weighted_rating != "UNKNOWN":
        if simple_rating != weighted_rating:
            rating_change = f"rating changed from {simple_rating} to {weighted_rating}"
        else:
            rating_change = f"rating unchanged ({weighted_rating})"
    else:
        rating_change = "rating change unavailable"

    failures_count = len(critical_failures) if isinstance(critical_failures, list) else 0

    explanation = (
        f"Journey-aware outcome evaluation: simple average score={_fmt_score(simple_average)}, "
        f"journey-weighted score={_fmt_score(weighted_score)}, {rating_change}. "
        f"Critical stage failures detected={failures_count}."
    )

    if failures_count > 0:
        top = _summarise_failure(critical_failures[0])
        explanation += f" Most severe example: {top}."

    return [VerificationEvidence(
        conversation_id=conversation_id,
        evidence_type=EvidenceType.outcome,
        related_signals=[],
        status=status,
        explanation=explanation,
    )]


def _rating_to_status(rating: str) -> EvidenceStatus:
    value = (rating or "").upper()
    if value == "PASS":
        return EvidenceStatus.pass_
    if value == "WARNING":
        return EvidenceStatus.warning
    if value == "FAIL":
        return EvidenceStatus.fail
    return EvidenceStatus.indeterminate


def _fmt_score(value: object) -> str:
    if isinstance(value, (int, float)):
        return f"{float(value):.4f}"
    return "n/a"


def _summarise_failure(item: object) -> str:
    if not isinstance(item, dict):
        return "details unavailable"
    turn_index = item.get("turn_index", "?")
    stage = item.get("stage", "unknown")
    score = item.get("score", "n/a")
    return f"turn={turn_index}, stage={stage}, score={score}"
