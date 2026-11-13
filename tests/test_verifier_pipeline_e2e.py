"""End-to-end smoke tests for the verification pipeline.

These tests verify that:

1. A nominal synthetic ExecutionTrace produces a PASS assessment.
2. A prompt-injection trace produces governance evidence (PASS — handled safely).
3. A loop-risk trace produces PASS_WITH_WARNINGS via the behaviour lane.
4. An execution-failure event produces operational evidence with warning status.
5. A two-turn conversation reaches a unified PASS assessment.
6. ADK adapter output — produced by normalise_adk_events_to_execution_trace —
   enters the shared signal-extraction and evidence-construction pipeline
   without modification (C1 integration test).
7. ADK loop-risk events produce the same loop_risk signal as the synthetic path.

Tests run without google-adk or any external service.
"""
from __future__ import annotations

import pytest

from workshop_verify_agents.adk_runtime.adk_trace_adapter import (
    normalise_adk_events_to_execution_trace,
)
from workshop_verify_agents.examples.conversations import get_scenario, list_scenarios
from workshop_verify_agents.verification.evidence_builder import build_evidence
from workshop_verify_agents.verification.evidence_schema import (
    AssessmentStatus,
    EvidenceStatus,
    EvidenceType,
)
from workshop_verify_agents.verification.offline_verifier import (
    verify_completed_conversation,
)
from workshop_verify_agents.verification.online_verifier import verify_turn_behaviour
from workshop_verify_agents.verification.signal_extractor import extract_signals
from workshop_verify_agents.verification.signal_schema import SignalSeverity, SignalType
from workshop_verify_agents.verification.trace_schema import ExecutionTrace, TraceEvent
from tests.fixtures.adk_event_fixtures import (
    injection_turn_events,
    loop_risk_turn_events,
    nominal_turn_events,
)

_CONV = "e2e-smoke-conv-001"


# ---------------------------------------------------------------------------
# Trace construction helpers (mirrors demo_offline_verification pattern)
# ---------------------------------------------------------------------------


def _make_nominal_trace(conversation_id: str = _CONV, turn_id: str = "turn-0") -> ExecutionTrace:
    trace = ExecutionTrace(conversation_id=conversation_id)
    for event_type, component, metadata in [
        ("safety_check_completed", "safety_layer", {"action": "allow", "reason": "clean"}),
        ("intent_classified", "intent_classifier", {"domain": "mortgage", "confidence": 0.85}),
        ("route_selected", "orchestrator", {"selected_domain": "mortgage"}),
        ("sub_agent_invoked", "mortgage_agent", {"domain": "mortgage", "topic": "eligibility"}),
        ("response_written", "response_writer", {"response_length": 220}),
    ]:
        trace.add_event(TraceEvent(
            conversation_id=conversation_id,
            turn_id=turn_id,
            component_name=component,
            event_type=event_type,
            metadata=metadata,
        ))
    return trace


def _make_injection_trace(conversation_id: str = _CONV, turn_id: str = "turn-inj") -> ExecutionTrace:
    trace = ExecutionTrace(conversation_id=conversation_id)
    trace.add_event(TraceEvent(
        conversation_id=conversation_id,
        turn_id=turn_id,
        component_name="safety_layer",
        event_type="safety_check_completed",
        metadata={
            "action": "allow",
            "prompt_injection_detected": True,
            "safe_response_delivered": True,
            "instructions_leaked": False,
            "redirection_present": True,
        },
    ))
    trace.add_event(TraceEvent(
        conversation_id=conversation_id,
        turn_id=turn_id,
        component_name="response_writer",
        event_type="response_written",
        metadata={"response_length": 80},
    ))
    return trace


def _make_loop_risk_trace(conversation_id: str = _CONV, turn_id: str = "turn-loop") -> ExecutionTrace:
    trace = ExecutionTrace(conversation_id=conversation_id)
    for _ in range(2):  # repeated route_selected triggers loop risk
        trace.add_event(TraceEvent(
            conversation_id=conversation_id,
            turn_id=turn_id,
            component_name="orchestrator",
            event_type="route_selected",
            metadata={"selected_domain": "investment"},
        ))
    for _ in range(2):  # repeated sub_agent_invoked
        trace.add_event(TraceEvent(
            conversation_id=conversation_id,
            turn_id=turn_id,
            component_name="investment_agent",
            event_type="sub_agent_invoked",
            metadata={"domain": "investment", "topic": "suitability"},
        ))
    trace.add_event(TraceEvent(
        conversation_id=conversation_id,
        turn_id=turn_id,
        component_name="response_writer",
        event_type="response_written",
        metadata={"response_length": 150},
    ))
    return trace


def _make_failure_trace(conversation_id: str = _CONV, turn_id: str = "turn-fail") -> ExecutionTrace:
    trace = ExecutionTrace(conversation_id=conversation_id)
    trace.add_event(TraceEvent(
        conversation_id=conversation_id,
        turn_id=turn_id,
        component_name="mortgage_agent",
        event_type="sub_agent_failed",
        metadata={"error": "timeout", "domain": "mortgage"},
    ))
    return trace


# ---------------------------------------------------------------------------
# 1. Nominal turn → PASS
# ---------------------------------------------------------------------------


def test_nominal_turn_produces_pass_assessment():
    trace = _make_nominal_trace()
    result = verify_turn_behaviour(_CONV, 0, trace)
    assert result.behaviour_assessment.overall_status == AssessmentStatus.pass_


def test_nominal_turn_produces_expected_signal_types():
    trace = _make_nominal_trace()
    result = verify_turn_behaviour(_CONV, 0, trace)
    signal_types = {s.signal_type for s in result.business_signals}
    assert SignalType.safety in signal_types
    assert SignalType.routing in signal_types
    assert SignalType.execution in signal_types


def test_nominal_turn_produces_behaviour_and_governance_evidence():
    trace = _make_nominal_trace()
    result = verify_turn_behaviour(_CONV, 0, trace)
    evidence_types = {e.evidence_type for e in result.behaviour_evidence}
    assert EvidenceType.governance in evidence_types
    assert EvidenceType.behaviour in evidence_types


# ---------------------------------------------------------------------------
# 2. Prompt-injection trace → governance PASS (handled safely)
# ---------------------------------------------------------------------------


def test_prompt_injection_handled_safely_produces_governance_pass():
    trace = _make_injection_trace()
    result = verify_turn_behaviour(_CONV, 0, trace)
    gov_items = [e for e in result.behaviour_evidence if e.evidence_type == EvidenceType.governance]
    assert gov_items, "Expected governance evidence for injection turn"
    assert all(e.status == EvidenceStatus.pass_ for e in gov_items)


def test_prompt_injection_signal_name_is_safety_compliance():
    trace = _make_injection_trace()
    result = verify_turn_behaviour(_CONV, 0, trace)
    safety_signals = [s for s in result.business_signals if s.signal_type == SignalType.safety]
    assert safety_signals
    assert all(s.signal_name == "safety_compliance" for s in safety_signals)


def test_prompt_injection_explanation_mentions_guardrail():
    trace = _make_injection_trace()
    result = verify_turn_behaviour(_CONV, 0, trace)
    safety_signals = [s for s in result.business_signals if s.signal_type == SignalType.safety]
    assert any("guardrail" in (s.explanation or "").lower() for s in safety_signals)


# ---------------------------------------------------------------------------
# 3. Loop-risk trace → PASS_WITH_WARNINGS
# ---------------------------------------------------------------------------


def test_loop_risk_turn_without_outcome_evidence_fails():
    """Rule 2: high-severity loop_risk with no outcome evidence → FAIL.

    verify_turn_behaviour is behaviour-only; it passes no outcome evidence to
    assess(), so Rule 2 fires.  PASS_WITH_WARNINGS requires outcome evidence
    (see test_loop_risk_conversation_with_outcome_produces_pass_with_warnings).
    """
    trace = _make_loop_risk_trace()
    result = verify_turn_behaviour(_CONV, 0, trace)
    assert result.behaviour_assessment.overall_status == AssessmentStatus.fail


def test_loop_risk_signal_produced():
    trace = _make_loop_risk_trace()
    signals = extract_signals(trace)
    loop_signals = [s for s in signals if s.signal_name == "loop_risk"]
    assert loop_signals, "Expected at least one loop_risk signal"
    assert all(s.severity == SignalSeverity.high for s in loop_signals)


def test_loop_risk_signal_maps_to_behaviour_evidence_with_warning_status():
    """loop_risk is in _BEHAVIOUR_SIGNAL_NAMES so it maps to behaviour evidence.
    High severity → warning status.
    """
    trace = _make_loop_risk_trace()
    signals = extract_signals(trace)
    evidence = build_evidence(signals, _CONV)
    beh_items = [e for e in evidence if e.evidence_type == EvidenceType.behaviour]
    assert beh_items, "Expected behaviour evidence from loop-risk trace"
    assert any(e.status == EvidenceStatus.warning for e in beh_items)


def test_loop_risk_conversation_with_outcome_produces_pass_with_warnings():
    """Rule 4 path: loop_risk behaviour warning + passing outcome evidence → PASS_WITH_WARNINGS.

    This is the paper's Trace Evidence Showcase result: the loop risk is visible
    as a warning, but the passing outcome prevents a FAIL under Rule 2.
    """
    turn_0 = _make_loop_risk_trace(_CONV, "turn-0")
    r0 = verify_turn_behaviour(_CONV, 0, turn_0)
    turns = [{"role": "user", "text": "Please continue with the guidance."}]
    unified = verify_completed_conversation(
        conversation_id=_CONV,
        behaviour_results=[r0],
        conversation_turns=turns,
        turn_scores=[0.87],
        journey_stage_labels=["follow_up"],
    )
    assert unified.final_assessment.overall_status == AssessmentStatus.pass_with_warnings


# ---------------------------------------------------------------------------
# 4. Execution failure → operational warning
# ---------------------------------------------------------------------------


def test_sub_agent_failure_produces_operational_evidence():
    trace = _make_failure_trace()
    result = verify_turn_behaviour(_CONV, 0, trace)
    op_items = [e for e in result.behaviour_evidence if e.evidence_type == EvidenceType.operational]
    assert op_items


def test_sub_agent_failure_signal_name():
    trace = _make_failure_trace()
    signals = extract_signals(trace)
    risk_signals = [s for s in signals if s.signal_name == "execution_reliability_risk"]
    assert risk_signals
    assert risk_signals[0].severity == SignalSeverity.high


# ---------------------------------------------------------------------------
# 5. Two-turn unified conversation → PASS
# ---------------------------------------------------------------------------


def test_two_turn_conversation_unified_pass():
    turn_0 = _make_nominal_trace(_CONV, "turn-0")
    turn_1 = _make_nominal_trace(_CONV, "turn-1")
    r0 = verify_turn_behaviour(_CONV, 0, turn_0)
    r1 = verify_turn_behaviour(_CONV, 1, turn_1)
    turns = [
        {"role": "user", "text": "What mortgage options do I have?"},
        {"role": "agent", "text": "You can consider fixed or variable rates."},
    ]
    unified = verify_completed_conversation(
        conversation_id=_CONV,
        behaviour_results=[r0, r1],
        conversation_turns=turns,
        turn_scores=[0.88, 0.91],
        journey_stage_labels=["discovery", "recommendation_or_guidance"],
    )
    assert unified.final_assessment.overall_status == AssessmentStatus.pass_
    assert unified.completeness == "offline_full"


def test_two_turn_unified_has_outcome_result():
    turn_0 = _make_nominal_trace(_CONV, "turn-0")
    r0 = verify_turn_behaviour(_CONV, 0, turn_0)
    turns = [{"role": "user", "text": "Help me."}]
    unified = verify_completed_conversation(
        conversation_id=_CONV,
        behaviour_results=[r0],
        conversation_turns=turns,
        turn_scores=[0.90],
        journey_stage_labels=["greeting"],
    )
    assert unified.outcome_result is not None


# ---------------------------------------------------------------------------
# 6. ADK adapter → shared pipeline (C1 integration test)
# ---------------------------------------------------------------------------


def test_adk_nominal_events_enter_pipeline_and_produce_pass():
    """ADK-normalised trace produces the same PASS assessment as the synthetic path.

    This test is the primary evidence for C1: events from the ADK-backed runtime
    enter the same downstream signal-extraction and evidence-construction pipeline
    without modification.
    """
    adk_trace = normalise_adk_events_to_execution_trace(nominal_turn_events("inv-adk"), "adk-conv")
    result = verify_turn_behaviour("adk-conv", 0, adk_trace)
    assert result.behaviour_assessment.overall_status == AssessmentStatus.pass_


def test_adk_nominal_events_produce_safety_signal():
    adk_trace = normalise_adk_events_to_execution_trace(nominal_turn_events(), _CONV)
    signals = extract_signals(adk_trace)
    safety = [s for s in signals if s.signal_type == SignalType.safety]
    assert safety, "Expected a safety signal from the ADK-normalised trace"
    assert safety[0].signal_name == "safety_compliance"


def test_adk_nominal_events_produce_routing_signal():
    adk_trace = normalise_adk_events_to_execution_trace(nominal_turn_events(), _CONV)
    signals = extract_signals(adk_trace)
    routing = [s for s in signals if s.signal_name == "intent_routing"]
    assert routing
    assert routing[0].value == "mortgage"


def test_adk_nominal_events_produce_governance_behaviour_operational_evidence():
    adk_trace = normalise_adk_events_to_execution_trace(nominal_turn_events(), _CONV)
    signals = extract_signals(adk_trace)
    evidence = build_evidence(signals, _CONV)
    evidence_types = {e.evidence_type for e in evidence}
    assert EvidenceType.governance in evidence_types
    assert EvidenceType.behaviour in evidence_types


def test_adk_injection_events_produce_governance_pass():
    """Prompt-injection handling through the ADK path produces governance PASS evidence."""
    adk_trace = normalise_adk_events_to_execution_trace(injection_turn_events(), _CONV)
    result = verify_turn_behaviour(_CONV, 0, adk_trace)
    gov = [e for e in result.behaviour_evidence if e.evidence_type == EvidenceType.governance]
    assert gov
    assert all(e.status == EvidenceStatus.pass_ for e in gov)


# ---------------------------------------------------------------------------
# 7. ADK loop-risk events → same signal as synthetic path
# ---------------------------------------------------------------------------


def test_adk_loop_risk_events_produce_loop_risk_signal():
    """Repeated ADK route_selected events trigger loop_risk via the shared extractor."""
    adk_trace = normalise_adk_events_to_execution_trace(loop_risk_turn_events(), _CONV)
    signals = extract_signals(adk_trace)
    loop_signals = [s for s in signals if s.signal_name == "loop_risk"]
    assert loop_signals, "Expected loop_risk signal from repeated ADK route_selected events"


def test_adk_loop_risk_turn_without_outcome_fails():
    """ADK loop-risk path follows the same Rule 2 policy as the synthetic path."""
    adk_trace = normalise_adk_events_to_execution_trace(loop_risk_turn_events(), _CONV)
    result = verify_turn_behaviour(_CONV, 0, adk_trace)
    assert result.behaviour_assessment.overall_status == AssessmentStatus.fail


def test_adk_loop_risk_conversation_with_outcome_produces_pass_with_warnings():
    """ADK path: loop-risk turn + passing outcome scores → PASS_WITH_WARNINGS.
    Mirrors the paper's Trace Evidence Showcase result through the ADK adapter.
    """
    adk_trace = normalise_adk_events_to_execution_trace(loop_risk_turn_events("inv-adk"), "adk-loop")
    r0 = verify_turn_behaviour("adk-loop", 0, adk_trace)
    turns = [{"role": "user", "text": "Please continue with the savings guidance."}]
    unified = verify_completed_conversation(
        conversation_id="adk-loop",
        behaviour_results=[r0],
        conversation_turns=turns,
        turn_scores=[0.87],
        journey_stage_labels=["follow_up"],
    )
    assert unified.final_assessment.overall_status == AssessmentStatus.pass_with_warnings


# ---------------------------------------------------------------------------
# 8. All five deterministic scenarios run without error (regression guard)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scenario_name", list_scenarios())
def test_all_deterministic_scenarios_complete_without_error(scenario_name):
    """Smoke test: every registered scenario must produce a unified result."""
    from workshop_verify_agents.demo_offline_verification import _build_demo_trace_for_exchange
    from workshop_verify_agents.examples.conversations import get_exchanges

    scenario = get_scenario(scenario_name)
    turns = list(scenario.get("turns", []))
    exchanges = get_exchanges(scenario)
    stages = [str(exchange["journey_stage"]) for exchange in exchanges]
    scores = [float(exchange["quality_score"]) for exchange in exchanges]
    conversation_id = f"smoke::{scenario_name}"

    behaviour_results = []
    for index, exchange in enumerate(exchanges):
        trace = _build_demo_trace_for_exchange(
            conversation_id=conversation_id,
            exchange_index=index,
            user_turn=turns[index * 2],
            agent_turn=turns[index * 2 + 1],
            journey_stage=str(exchange["journey_stage"]),
        )
        behaviour_results.append(verify_turn_behaviour(conversation_id, index, trace))

    unified = verify_completed_conversation(
        conversation_id=conversation_id,
        behaviour_results=behaviour_results,
        conversation_turns=turns,
        turn_scores=scores,
        journey_stage_labels=stages,
        conversation_exchanges=exchanges,
    )
    assert unified.final_assessment.overall_status in list(AssessmentStatus)
    assert unified.completeness in {"offline_full", "offline_missing_outcome", "online_behaviour_only"}


def _run_registered_scenario(scenario_name):
    """Run one registered scenario through exchange-level deterministic verification."""
    from workshop_verify_agents.demo_offline_verification import _build_demo_trace_for_exchange
    from workshop_verify_agents.examples.conversations import get_exchanges

    scenario = get_scenario(scenario_name)
    turns = list(scenario["turns"])
    exchanges = get_exchanges(scenario)
    conversation_id = f"taxonomy::{scenario_name}"
    results = [
        verify_turn_behaviour(
            conversation_id,
            index,
            _build_demo_trace_for_exchange(
                conversation_id,
                index,
                turns[index * 2],
                turns[index * 2 + 1],
                str(exchange["journey_stage"]),
            ),
        )
        for index, exchange in enumerate(exchanges)
    ]
    return verify_completed_conversation(
        conversation_id,
        results,
        turns,
        [float(exchange["quality_score"]) for exchange in exchanges],
        [str(exchange["journey_stage"]) for exchange in exchanges],
        exchanges,
    )


def test_s1_no_policy_intervention_is_pass():
    result = _run_registered_scenario("mortgage_happy_path")
    assert result.final_assessment.overall_status == AssessmentStatus.pass_
    assert all(not item.policy_verification_results for item in result.behaviour_results)


def test_s2_handled_prompt_injection_is_pass_with_provenance():
    result = _run_registered_scenario("investment_prompt_injection_handled")
    policies = [p for item in result.behaviour_results for p in item.policy_verification_results]
    assert len(policies) == 1
    assert policies[0].risk_detected is True
    assert policies[0].control_effective is True
    assert result.final_assessment.overall_status == AssessmentStatus.pass_
    governance = [e for item in result.behaviour_results for e in item.behaviour_evidence
                  if e.evidence_type == EvidenceType.governance and e.control_observation]
    assert governance


def test_s3_guaranteed_return_policy_failure_is_governance_fail():
    result = _run_registered_scenario("investment_guaranteed_return_policy_failure")
    policies = [p for item in result.behaviour_results for p in item.policy_verification_results]
    assert len(policies) == 1
    assert policies[0].risk_type.value == "guaranteed_return_request"
    assert policies[0].control_effective is False
    assert result.final_assessment.overall_status == AssessmentStatus.fail
    assert any("Governance FAIL" in failure for failure in result.final_assessment.failures)


def test_s4_is_outcome_warning_with_clean_behaviour():
    result = _run_registered_scenario("mortgage_hidden_eligibility_failure")
    assert result.final_assessment.overall_status == AssessmentStatus.pass_with_warnings
    assert all(not item.policy_verification_results for item in result.behaviour_results)
    assert result.outcome_result is not None
    assert result.outcome_result.journey_aware_result["journey_weighted_rating"] == "WARNING"


def test_s5_is_outcome_failure_with_clean_behaviour():
    result = _run_registered_scenario("investment_suitability_failure")
    assert result.final_assessment.overall_status == AssessmentStatus.fail
    assert all(not item.policy_verification_results for item in result.behaviour_results)
    assert result.outcome_result is not None
    assert result.outcome_result.journey_aware_result["journey_weighted_rating"] == "FAIL"
