from workshop_verify_agents.verification.evidence_schema import (
    AssessmentStatus,
    EvidenceStatus,
    EvidenceType,
    VerificationEvidence,
)
from workshop_verify_agents.verification.verification_assessor import assess


def _evidence(
    evidence_type: EvidenceType,
    status: EvidenceStatus,
    explanation: str,
) -> VerificationEvidence:
    return VerificationEvidence(
        conversation_id="conv-1",
        evidence_type=evidence_type,
        related_signals=[],
        status=status,
        explanation=explanation,
    )


def test_behaviour_pass_outcome_pass_is_pass() -> None:
    evidence_items = [
        _evidence(EvidenceType.behaviour, EvidenceStatus.pass_, "behaviour ok"),
        _evidence(EvidenceType.outcome, EvidenceStatus.pass_, "outcome ok"),
    ]

    assessment = assess(evidence_items, [], "conv-1")

    assert assessment.overall_status == AssessmentStatus.pass_
    assert "Behaviour evidence statuses" in (assessment.summary or "")
    assert "Outcome evidence statuses" in (assessment.summary or "")


def test_behaviour_pass_outcome_warning_is_pass_with_warnings() -> None:
    evidence_items = [
        _evidence(EvidenceType.behaviour, EvidenceStatus.pass_, "behaviour ok"),
        _evidence(EvidenceType.outcome, EvidenceStatus.warning, "outcome warning"),
    ]

    assessment = assess(evidence_items, [], "conv-1")

    assert assessment.overall_status == AssessmentStatus.pass_with_warnings


def test_behaviour_pass_outcome_fail_is_fail() -> None:
    evidence_items = [
        _evidence(EvidenceType.behaviour, EvidenceStatus.pass_, "behaviour ok"),
        _evidence(EvidenceType.outcome, EvidenceStatus.fail, "journey-aware fail"),
    ]

    assessment = assess(evidence_items, [], "conv-1")

    assert assessment.overall_status == AssessmentStatus.fail
    assert any("Outcome FAIL" in message for message in assessment.failures)


def test_governance_fail_is_fail() -> None:
    evidence_items = [
        _evidence(EvidenceType.governance, EvidenceStatus.fail, "governance breach"),
        _evidence(EvidenceType.outcome, EvidenceStatus.pass_, "outcome ok"),
    ]

    assessment = assess(evidence_items, [], "conv-1")

    assert assessment.overall_status == AssessmentStatus.fail
    assert any("Governance FAIL" in message for message in assessment.failures)


def test_no_evidence_is_indeterminate() -> None:
    assessment = assess([], [], "conv-1")

    assert assessment.overall_status == AssessmentStatus.indeterminate
