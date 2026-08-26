"""Produce a VerificationAssessment from a list of VerificationEvidence items.

Decision logic
--------------
The assessor applies rules in priority order (first match wins):

  1. FAIL — any governance evidence has status=fail (critical safety/policy breach).
  2. FAIL — any behaviour evidence contains a loop_risk signal at high+ severity
             AND no successful outcome evidence is present.
  3. VERIFIED_WITH_WARNINGS — operational evidence contains an execution failure
             (execution_reliability_risk) but outcome evidence is still pass/warning.
  4. VERIFIED_WITH_WARNINGS — any evidence dimension is warning.
  5. VERIFIED — all assessed dimensions are pass.
  6. INDETERMINATE — no evidence items were produced.

The assessor is intentionally simple and transparent so that its decisions
can be explained and critiqued in the research paper.

Public API
----------
    assess(evidence_items, signals, conversation_id) -> VerificationAssessment
"""

from __future__ import annotations

from collections import defaultdict

from workshop_verify_agents.verification.evidence_schema import (
    AssessmentStatus,
    EvidenceStatus,
    EvidenceType,
    VerificationAssessment,
    VerificationEvidence,
)
from workshop_verify_agents.verification.signal_schema import (
    BusinessSignal,
    SignalSeverity,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def assess(
    evidence_items: list[VerificationEvidence],
    signals: list[BusinessSignal],
    conversation_id: str,
) -> VerificationAssessment:
    """Apply assessment rules and return a ``VerificationAssessment``.

    Parameters
    ----------
    evidence_items:
        Output of ``evidence_builder.build_evidence()``.
    signals:
        The full flat list of ``BusinessSignal`` objects (used for fine-grained
        rule checks that look at individual signal names).
    conversation_id:
        Passed through to the assessment record.
    """
    if not evidence_items:
        return VerificationAssessment(
            conversation_id=conversation_id,
            overall_status=AssessmentStatus.indeterminate,
            summary="No evidence items were produced — cannot assess this conversation.",
        )

    failures: list[str] = []
    warnings: list[str] = []

    # Group evidence by type; preserve multiple items per dimension.
    by_type: dict[EvidenceType, list[VerificationEvidence]] = defaultdict(list)
    for item in evidence_items:
        by_type[item.evidence_type].append(item)

    def _add_warning(message: str) -> None:
        if message not in warnings:
            warnings.append(message)

    # ── Rule 1: critical governance failure ──────────────────────────────
    governance_items = by_type.get(EvidenceType.governance, [])
    for gov in governance_items:
        if gov.status == EvidenceStatus.fail:
            failures.append(
                f"Governance FAIL: {gov.explanation}"
            )

    # ── Rule 1b: any outcome-level fail (including journey-aware) ─────────
    outcome_items = by_type.get(EvidenceType.outcome, [])
    for out in outcome_items:
        if out.status == EvidenceStatus.fail:
            failures.append(
                "Outcome FAIL (journey-aware/outcome-level evidence): "
                f"{out.explanation}"
            )

    # ── Rule 2: loop risk with no successful outcome ──────────────────────
    loop_signal_ids = {
        s.signal_id for s in signals if s.signal_name == "loop_risk"
        and s.severity.numeric >= SignalSeverity.high.numeric
    }
    has_outcome_fail = any(item.status == EvidenceStatus.fail for item in outcome_items)
    has_success_like_outcome = any(
        item.status in (EvidenceStatus.pass_, EvidenceStatus.warning)
        for item in outcome_items
    )
    outcome_ok = has_success_like_outcome and not has_outcome_fail
    if loop_signal_ids and not outcome_ok:
        failures.append(
            "Behaviour FAIL: routing loop detected and no successful outcome evidence. "
            "The agent may have failed to deliver a response."
        )

    # ── Rule 3: execution failure but outcome still available ─────────────
    exec_failure_signals = [
        s for s in signals if s.signal_name == "execution_reliability_risk"
    ]
    if exec_failure_signals and outcome_ok:
        _add_warning(
            "Operational WARNING: one or more tool/sub-agent failures were recorded, "
            "but the conversation still produced an outcome. "
            f"Failed components: {', '.join(s.value or '?' for s in exec_failure_signals)}."
        )

    # ── Rule 4: any dimension at warning status ───────────────────────────
    for ev in evidence_items:
        if ev.status == EvidenceStatus.warning:
            _add_warning(
                f"{ev.evidence_type.value.capitalize()} WARNING: {ev.explanation}"
            )

    # ── Derive overall status ─────────────────────────────────────────────
    if failures:
        overall = AssessmentStatus.fail
    elif warnings:
        overall = AssessmentStatus.pass_with_warnings
    elif all(e.status == EvidenceStatus.pass_ for e in evidence_items):
        overall = AssessmentStatus.pass_
    else:
        overall = AssessmentStatus.indeterminate

    summary = _build_summary(overall, evidence_items, failures, warnings)

    return VerificationAssessment(
        conversation_id=conversation_id,
        overall_status=overall,
        evidence_items=evidence_items,
        warnings=warnings,
        failures=failures,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_summary(
    overall: AssessmentStatus,
    evidence_items: list[VerificationEvidence],
    failures: list[str],
    warnings: list[str],
) -> str:
    """Compose a single-paragraph narrative summary of the assessment."""
    status_phrase = {
        AssessmentStatus.pass_:               "The conversation passed all verification checks.",
        AssessmentStatus.pass_with_warnings:   "The conversation passed verification with warnings.",
        AssessmentStatus.fail:                 "The conversation FAILED verification.",
        AssessmentStatus.indeterminate:        "Verification is indeterminate.",
    }[overall]

    dim_statuses = ", ".join(
        f"{e.evidence_type.value}={e.status.value}" for e in evidence_items
    )

    behaviour_items = [e for e in evidence_items if e.evidence_type in {
        EvidenceType.behaviour,
        EvidenceType.governance,
        EvidenceType.operational,
    }]
    outcome_items = [e for e in evidence_items if e.evidence_type == EvidenceType.outcome]

    behaviour_statuses = ", ".join(e.status.value for e in behaviour_items) or "none"
    outcome_statuses = ", ".join(e.status.value for e in outcome_items) or "none"

    parts = [status_phrase, f"Evidence dimensions assessed: [{dim_statuses}]."]

    if behaviour_items and outcome_items:
        parts.append(
            f"Behaviour evidence statuses=[{behaviour_statuses}]; "
            f"Outcome evidence statuses=[{outcome_statuses}]."
        )

    if failures:
        parts.append(f"{len(failures)} failure(s) recorded.")
    if warnings:
        parts.append(f"{len(warnings)} warning(s) recorded.")

    return "  ".join(parts)
