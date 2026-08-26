"""Group BusinessSignal objects into typed VerificationEvidence items.

Signal-to-evidence dimension mapping
-------------------------------------
  safety, governance          → EvidenceType.governance
  routing, journey, loop_risk → EvidenceType.behaviour
  execution, operational      → EvidenceType.operational
  outcome                     → EvidenceType.outcome
  experience                  → EvidenceType.experience

Public API
----------
    build_evidence(signals, conversation_id) -> list[VerificationEvidence]
"""

from __future__ import annotations

from workshop_verify_agents.verification.evidence_schema import (
    EvidenceStatus,
    EvidenceType,
    VerificationEvidence,
)
from workshop_verify_agents.verification.policy_schema import PolicyVerificationResult
from workshop_verify_agents.verification.signal_schema import (
    BusinessSignal,
    SignalSeverity,
    SignalType,
)


# ---------------------------------------------------------------------------
# Signal → evidence dimension routing table
# ---------------------------------------------------------------------------

_SIGNAL_TYPE_TO_EVIDENCE: dict[SignalType, EvidenceType] = {
    SignalType.safety:      EvidenceType.governance,
    SignalType.governance:  EvidenceType.governance,
    SignalType.routing:     EvidenceType.behaviour,
    SignalType.journey:     EvidenceType.behaviour,
    SignalType.operational: EvidenceType.operational,
    SignalType.execution:   EvidenceType.operational,
    SignalType.outcome:     EvidenceType.outcome,
    SignalType.experience:  EvidenceType.experience,
}

# loop_risk is emitted as SignalType.operational; it also belongs to behaviour.
# We promote it to behaviour by checking signal_name explicitly.
_BEHAVIOUR_SIGNAL_NAMES = {"loop_risk", "journey_routing", "intent_routing"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_evidence(
    signals: list[BusinessSignal],
    conversation_id: str,
) -> list[VerificationEvidence]:
    """Group *signals* into one ``VerificationEvidence`` per evidence dimension.

    Only dimensions that have at least one contributing signal are included in
    the returned list.  Each item carries an EvidenceStatus derived from the
    worst-case severity of its contributing signals, plus a narrative explanation.
    """
    # Bucket signals by evidence dimension
    buckets: dict[EvidenceType, list[BusinessSignal]] = {}
    for sig in signals:
        dim = _dimension(sig)
        buckets.setdefault(dim, []).append(sig)

    evidence_items: list[VerificationEvidence] = []
    for dim, bucket_signals in buckets.items():
        status = _derive_status(bucket_signals)
        explanation = _narrative(dim, bucket_signals, status)
        evidence_items.append(VerificationEvidence(
            conversation_id=conversation_id,
            evidence_type=dim,
            related_signals=[s.signal_id for s in bucket_signals],
            status=status,
            explanation=explanation,
        ))

    # Return in a consistent order for deterministic output
    order = list(EvidenceType)
    evidence_items.sort(key=lambda e: order.index(e.evidence_type))
    return evidence_items


def build_policy_evidence(
    policy_results: list[PolicyVerificationResult],
    conversation_id: str,
) -> list[VerificationEvidence]:
    """Build governance evidence directly from policy-verification results.

    Policy results interpret existing business signals and trace metadata; they
    are evidence inputs, not a second business-signal hierarchy.
    """
    return [
        VerificationEvidence(
            conversation_id=conversation_id,
            evidence_type=EvidenceType.governance,
            related_signals=list(result.source_signal_ids),
            status=result.evidence_status,
            explanation=result.explanation,
            control_observation=(
                f"risk_type={result.risk_type.value}; "
                f"policy_type={result.policy_type.value}; "
                f"risk_detected={result.risk_detected}; "
                f"control_effective={result.control_effective}; "
                f"policy_compliant={result.policy_compliant}; "
                f"source_event_ids={','.join(result.source_event_ids)}"
            ),
        )
        for result in policy_results
    ]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _dimension(signal: BusinessSignal) -> EvidenceType:
    """Map one signal to its evidence dimension."""
    if signal.signal_name in _BEHAVIOUR_SIGNAL_NAMES:
        return EvidenceType.behaviour
    return _SIGNAL_TYPE_TO_EVIDENCE.get(signal.signal_type, EvidenceType.operational)


def _derive_status(signals: list[BusinessSignal]) -> EvidenceStatus:
    """Derive EvidenceStatus from the worst-case severity in *signals*."""
    if not signals:
        return EvidenceStatus.indeterminate

    worst = max(signals, key=lambda s: s.severity.numeric)

    if worst.severity == SignalSeverity.critical:
        return EvidenceStatus.fail
    if worst.severity == SignalSeverity.high:
        return EvidenceStatus.warning
    if worst.severity == SignalSeverity.medium:
        return EvidenceStatus.warning
    return EvidenceStatus.pass_


def _narrative(
    dim: EvidenceType,
    signals: list[BusinessSignal],
    status: EvidenceStatus,
) -> str:
    """Produce a short human-readable summary for one evidence dimension."""
    n = len(signals)
    names = ", ".join(f"'{s.signal_name}'" for s in signals[:3])
    if n > 3:
        names += f" … and {n - 3} more"

    status_label = {
        EvidenceStatus.pass_:          "passed",
        EvidenceStatus.warning:        "passed with warnings",
        EvidenceStatus.fail:           "FAILED",
        EvidenceStatus.indeterminate:  "indeterminate",
    }[status]

    dim_descriptions = {
        EvidenceType.governance:   "Safety and governance controls",
        EvidenceType.behaviour:    "Agent routing and journey behaviour",
        EvidenceType.operational:  "Execution and operational reliability",
        EvidenceType.outcome:      "Conversation outcome availability",
        EvidenceType.experience:   "Customer experience quality",
    }

    prefix = dim_descriptions.get(dim, dim.value.capitalize())
    detail = _worst_signal_detail(signals)
    return f"{prefix} {status_label}. Signals contributing: {names}.{detail}"


def _worst_signal_detail(signals: list[BusinessSignal]) -> str:
    """Return an extra sentence describing the most severe signal, if notable."""
    notable = [
        s for s in signals
        if s.severity in (SignalSeverity.critical, SignalSeverity.high)
    ]
    if not notable:
        return ""
    worst = max(notable, key=lambda s: s.severity.numeric)
    return f" Most severe: '{worst.signal_name}' ({worst.severity.value}) — {worst.explanation}"
