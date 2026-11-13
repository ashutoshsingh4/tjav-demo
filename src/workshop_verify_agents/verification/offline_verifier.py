"""Offline verifier for conversation-level behaviour + outcome assessment."""

from __future__ import annotations

from typing import Literal

from workshop_verify_agents.journey.journey_classifier import classify_conversation
from workshop_verify_agents.journey.journey_weighted_scorer import compare_scoring_methods
from workshop_verify_agents.verification.evidence_builder import (
    build_evidence,
    build_policy_evidence,
)
from workshop_verify_agents.verification.evidence_schema import EvidenceType
from workshop_verify_agents.verification.journey_outcome_adapter import (
    build_outcome_evidence_from_journey_result,
)
from workshop_verify_agents.verification.signal_schema import BusinessSignal
from workshop_verify_agents.verification.verification_assessor import assess
from workshop_verify_agents.verification.verification_results import (
    ConversationOutcomeResult,
    TurnBehaviourResult,
    UnifiedConversationResult,
)

_BEHAVIOUR_EVIDENCE_TYPES = {
    EvidenceType.behaviour,
    EvidenceType.governance,
    EvidenceType.operational,
}


def verify_completed_conversation(
    conversation_id: str,
    behaviour_results: list[TurnBehaviourResult],
    conversation_turns: list[dict],
    turn_scores: list[float] | None = None,
    journey_stage_labels: list[str] | None = None,
    conversation_exchanges: list[dict] | None = None,
    assessment_mode: Literal["journey_only", "behaviour_only", "unified"] = "unified",
) -> UnifiedConversationResult:
    """Run offline conversation-level unified verification.

    Behaviour evidence is aggregated from per-turn traces/signals.
    Journey-aware outcome evidence is produced only when conversation-level
    scores are provided.
    """
    all_signals: list[BusinessSignal] = []
    for result in behaviour_results:
        all_signals.extend(result.business_signals)

    all_policy_results = [
        policy
        for result in behaviour_results
        for policy in result.policy_verification_results
    ]
    all_evidence = [
        *build_evidence(all_signals, conversation_id),
        *build_policy_evidence(all_policy_results, conversation_id),
    ]
    behaviour_evidence_conversation_scope = [
        item for item in all_evidence
        if item.evidence_type in _BEHAVIOUR_EVIDENCE_TYPES
    ]

    outcome_result: ConversationOutcomeResult | None = None
    outcome_evidence = []
    completeness = "offline_missing_outcome"
    warnings: list[str] = []

    if turn_scores is not None:
        outcome_turns = conversation_exchanges or conversation_turns
        labels = journey_stage_labels
        if labels is None:
            labels = [
                item.stage.value
                for item in classify_conversation(outcome_turns)
            ]

        expected_turn_count = len(outcome_turns)
        scores_match_turns = len(turn_scores) == expected_turn_count
        labels_match_scores = len(labels) == len(turn_scores)

        if not scores_match_turns or not labels_match_scores:
            warnings.append(
                "Outcome evidence was not computed because turn score inputs were inconsistent."
            )
            warnings.append(
                "Expected lengths: conversation_turns="
                f"{expected_turn_count}, journey_stage_labels={len(labels)}, "
                f"turn_scores={len(turn_scores)}."
            )

        if scores_match_turns and labels_match_scores:
            journey_result = compare_scoring_methods(
                turn_scores=turn_scores,
                journey_stages=labels,
            )
            outcome_evidence = build_outcome_evidence_from_journey_result(
                conversation_id=conversation_id,
                journey_result=journey_result,
            )
            outcome_result = ConversationOutcomeResult(
                conversation_id=conversation_id,
                journey_stage_labels=list(labels),
                turn_scores=[float(score) for score in turn_scores],
                journey_aware_result=journey_result,
                outcome_evidence=outcome_evidence,
            )
            completeness = "offline_full"

    if assessment_mode == "journey_only":
        assessment_evidence = outcome_evidence
    elif assessment_mode == "behaviour_only":
        assessment_evidence = behaviour_evidence_conversation_scope
    else:
        assessment_evidence = [
            *behaviour_evidence_conversation_scope,
            *outcome_evidence,
        ]

    final_assessment = assess(
        evidence_items=assessment_evidence,
        signals=all_signals,
        conversation_id=conversation_id,
        allow_missing_outcome=assessment_mode == "behaviour_only",
    )

    return UnifiedConversationResult(
        conversation_id=conversation_id,
        behaviour_results=behaviour_results,
        behaviour_evidence_conversation_scope=behaviour_evidence_conversation_scope,
        outcome_result=outcome_result,
        final_assessment=final_assessment,
        assessment_mode=assessment_mode,
        warnings=warnings,
        completeness=completeness,
    )
