"""Online verifier for turn-level behaviour verification from traces."""

from __future__ import annotations

from workshop_verify_agents.verification.evidence_builder import (
    build_evidence,
    build_policy_evidence,
)
from workshop_verify_agents.verification.evidence_schema import EvidenceType
from workshop_verify_agents.verification.signal_extractor import extract_signals
from workshop_verify_agents.verification.signal_schema import SignalType
from workshop_verify_agents.verification.trace_schema import ExecutionTrace
from workshop_verify_agents.verification.verification_assessor import assess
from workshop_verify_agents.verification.verification_results import TurnBehaviourResult
from workshop_verify_agents.verification.policy_verifier import verify_policies


_BEHAVIOUR_EVIDENCE_TYPES = {
    EvidenceType.behaviour,
    EvidenceType.governance,
    EvidenceType.operational,
}

_BEHAVIOUR_SIGNAL_TYPES = {
    SignalType.routing,
    SignalType.safety,
    SignalType.governance,
    SignalType.execution,
    SignalType.operational,
    SignalType.journey,
}


def verify_turn_behaviour(
    conversation_id: str,
    turn_index: int,
    execution_trace: ExecutionTrace,
) -> TurnBehaviourResult:
    """Verify behaviour from a single ExecutionTrace in online mode.

    This function intentionally excludes journey-aware outcome evidence. It
    returns behaviour, governance, and operational evidence only.
    """
    signals = extract_signals(execution_trace)
    policy_results = verify_policies(execution_trace, signals)
    all_evidence = [
        *build_evidence(signals, conversation_id),
        *build_policy_evidence(policy_results, conversation_id),
    ]
    behaviour_evidence = [
        item for item in all_evidence
        if item.evidence_type in _BEHAVIOUR_EVIDENCE_TYPES
    ]
    behaviour_signals = [
        signal for signal in signals
        if signal.signal_type in _BEHAVIOUR_SIGNAL_TYPES
    ]
    behaviour_assessment = assess(
        evidence_items=behaviour_evidence,
        signals=behaviour_signals,
        conversation_id=conversation_id,
    )

    return TurnBehaviourResult(
        conversation_id=conversation_id,
        turn_index=turn_index,
        execution_trace=execution_trace,
        business_signals=signals,
        policy_verification_results=policy_results,
        behaviour_evidence=behaviour_evidence,
        behaviour_assessment=behaviour_assessment,
    )
