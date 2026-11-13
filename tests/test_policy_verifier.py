"""Tests for policy interpretation and direct policy evidence construction."""
from __future__ import annotations

from workshop_verify_agents.verification.evidence_builder import build_policy_evidence
from workshop_verify_agents.verification.evidence_schema import AssessmentStatus, EvidenceStatus, EvidenceType
from workshop_verify_agents.verification.policy_verifier import verify_policies
from workshop_verify_agents.verification.signal_extractor import extract_signals
from workshop_verify_agents.verification.trace_schema import ExecutionTrace, TraceEvent
from workshop_verify_agents.verification.online_verifier import verify_turn_behaviour


def _trace(*events: tuple[str, dict]) -> ExecutionTrace:
    trace = ExecutionTrace(conversation_id="policy-test")
    for event_type, metadata in events:
        trace.add_event(TraceEvent(
            conversation_id="policy-test",
            turn_id="turn-0",
            component_name="test",
            event_type=event_type,
            metadata=metadata,
        ))
    return trace


def test_clean_trace_has_no_policy_result():
    trace = _trace(("safety_check_completed", {"action": "allow"}))
    assert verify_policies(trace, extract_signals(trace)) == []


def test_prompt_injection_handled_is_pass_and_requires_redirection():
    trace = _trace(("safety_check_completed", {
        "action": "allow", "prompt_injection_detected": True,
        "safe_response_delivered": True, "instructions_leaked": False,
        "redirection_present": True,
    }))
    results = verify_policies(trace, extract_signals(trace))
    assert len(results) == 1
    result = results[0]
    assert result.control_effective is True
    assert result.policy_compliant is True
    assert result.evidence_status == EvidenceStatus.pass_


def test_prompt_injection_without_redirection_is_fail():
    trace = _trace(("safety_check_completed", {
        "action": "allow", "prompt_injection_detected": True,
        "safe_response_delivered": True, "instructions_leaked": False,
        "redirection_present": False,
    }))
    result = verify_policies(trace, extract_signals(trace))[0]
    assert result.control_effective is False
    assert result.evidence_status == EvidenceStatus.fail


def test_guaranteed_return_response_violation_is_fail():
    trace = _trace(
        ("safety_check_completed", {"action": "allow", "guaranteed_return_request": True}),
        ("response_written", {
            "response_length": 70, "guarantee_language_present": True,
            "disclaimer_present": False, "uncertainty_statement_present": False,
        }),
    )
    result = verify_policies(trace, extract_signals(trace))[0]
    assert result.control_effective is False
    assert result.policy_compliant is False
    assert result.evidence_status == EvidenceStatus.fail
    assert result.guarantee_language_present is True


def test_guaranteed_return_correct_control_is_pass():
    trace = _trace(
        ("safety_check_completed", {"action": "allow", "guaranteed_return_request": True}),
        ("response_written", {
            "response_length": 70, "guarantee_language_present": False,
            "disclaimer_present": True, "uncertainty_statement_present": True,
        }),
    )
    result = verify_policies(trace, extract_signals(trace))[0]
    assert result.control_effective is True
    assert result.evidence_status == EvidenceStatus.pass_


def test_policy_result_becomes_direct_governance_evidence():
    trace = _trace(("safety_check_completed", {
        "action": "allow", "prompt_injection_detected": True,
        "safe_response_delivered": True, "instructions_leaked": False,
        "redirection_present": True,
    }))
    results = verify_policies(trace, extract_signals(trace))
    evidence = build_policy_evidence(results, "policy-test")
    assert len(evidence) == 1
    assert evidence[0].evidence_type == EvidenceType.governance
    assert evidence[0].status == EvidenceStatus.pass_
    assert "control_effective=True" in (evidence[0].control_observation or "")


def test_handled_injection_online_assessment_is_pass():
    trace = _trace(("safety_check_completed", {
        "action": "allow", "prompt_injection_detected": True,
        "safe_response_delivered": True, "instructions_leaked": False,
        "redirection_present": True,
    }), ("response_written", {"response_length": 80}))
    result = verify_turn_behaviour("policy-test", 0, trace)
    assert result.behaviour_assessment.overall_status == AssessmentStatus.pass_
    assert len(result.policy_verification_results) == 1
