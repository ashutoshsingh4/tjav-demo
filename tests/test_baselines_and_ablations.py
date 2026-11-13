from workshop_verify_agents.journey.journey_weighted_scorer import (
    critical_stage_gate_baseline,
    critical_stage_only_baseline,
    minimum_turn_baseline,
)
from workshop_verify_agents.verification.evidence_schema import (
    AssessmentStatus,
    EvidenceStatus,
    EvidenceType,
    VerificationEvidence,
)
from workshop_verify_agents.verification.offline_verifier import verify_completed_conversation
from workshop_verify_agents.verification.verification_assessor import assess


def _evidence(evidence_type: EvidenceType, status: EvidenceStatus) -> VerificationEvidence:
    return VerificationEvidence(
        conversation_id="conv-1",
        evidence_type=evidence_type,
        status=status,
        explanation=f"{evidence_type.value} {status.value}",
    )


def test_minimum_turn_baseline_uses_lowest_score_and_provenance() -> None:
    result = minimum_turn_baseline(
        [0.90, 0.61, 0.80],
        ["greeting", "closing", "discovery"],
        ["turn-a", "turn-b", "turn-c"],
    )

    assert result.score == 0.61
    assert result.rating == "WARNING"
    assert result.turn_ids_included == ["turn-a", "turn-b", "turn-c"]
    assert result.provenance == ["turn:turn-a", "turn:turn-b", "turn:turn-c"]


def test_critical_stage_only_ignores_noncritical_stages() -> None:
    result = critical_stage_only_baseline(
        [0.10, 0.80, 0.20],
        ["greeting", "eligibility_or_suitability", "closing"],
    )

    assert result.score == 0.80
    assert result.rating == "PASS"
    assert result.stages_included == ["eligibility_or_suitability"]


def test_critical_stage_only_is_not_applicable_without_critical_stage() -> None:
    result = critical_stage_only_baseline([0.90], ["greeting"])

    assert result.score is None
    assert result.rating == "NOT_APPLICABLE"
    assert "not applicable" in result.explanation.lower()


def test_critical_stage_gate_uses_fail_then_warning_precedence() -> None:
    failing = critical_stage_gate_baseline(
        [0.99, 0.55], ["greeting", "eligibility_or_suitability"]
    )
    warning = critical_stage_gate_baseline(
        [0.99, 0.7499], ["greeting", "eligibility_or_suitability"]
    )

    assert failing.rating == "WARNING"
    assert warning.rating == "WARNING"
    assert failing.score == 0.77


def test_critical_stage_gate_boundary_at_warning_threshold_falls_back_to_flat_mean() -> None:
    result = critical_stage_gate_baseline(
        [0.99, 0.75], ["greeting", "eligibility_or_suitability"]
    )

    assert result.rating == "PASS"
    assert "flat-mean" in result.explanation


def test_assessor_governance_fail_overrides_warning() -> None:
    assessment = assess(
        [
            _evidence(EvidenceType.governance, EvidenceStatus.fail),
            _evidence(EvidenceType.outcome, EvidenceStatus.warning),
        ],
        [],
        "conv-1",
    )

    assert assessment.overall_status == AssessmentStatus.fail


def test_assessor_outcome_fail_overrides_behaviour_pass() -> None:
    assessment = assess(
        [
            _evidence(EvidenceType.behaviour, EvidenceStatus.pass_),
            _evidence(EvidenceType.outcome, EvidenceStatus.fail),
        ],
        [],
        "conv-1",
    )

    assert assessment.overall_status == AssessmentStatus.fail


def test_offline_assessment_modes_select_only_requested_lane() -> None:
    result = verify_completed_conversation(
        conversation_id="conv-1",
        behaviour_results=[],
        conversation_turns=[{"role": "user", "text": "Help"}],
        turn_scores=[0.90],
        journey_stage_labels=["greeting"],
        assessment_mode="journey_only",
    )

    assert result.assessment_mode == "journey_only"
    assert result.final_assessment.overall_status == AssessmentStatus.pass_
    assert all(item.evidence_type == EvidenceType.outcome
               for item in result.final_assessment.evidence_items)
