from workshop_verify_agents.demo_offline_verification import _run_scenario
from workshop_verify_agents.examples.conversations import list_scenarios
from workshop_verify_agents.verification.evidence_schema import AssessmentStatus
from workshop_verify_agents.verification.verification_assessor import assess


def _behaviour_result(name: str):
    return _run_scenario(name, "behaviour_only")[2]


def _events(result):
    return [
        event
        for behaviour_result in result.behaviour_results
        for event in behaviour_result.execution_trace.events
    ]


def test_loop_and_routing_warnings_pass_behaviour_only() -> None:
    assert _behaviour_result("loop_risk").final_assessment.overall_status == AssessmentStatus.pass_with_warnings
    assert _behaviour_result("routing_failure").final_assessment.overall_status == AssessmentStatus.pass_with_warnings


def test_policy_and_escalation_failures_fail_behaviour_only() -> None:
    assert _behaviour_result("unhandled_prompt_injection").final_assessment.overall_status == AssessmentStatus.fail
    assert _behaviour_result("missing_escalation").final_assessment.overall_status == AssessmentStatus.fail


def test_empty_behaviour_evidence_is_indeterminate() -> None:
    result = assess([], [], "empty-behaviour")

    assert result.overall_status == AssessmentStatus.indeterminate


def test_recovery_paths_emit_distinct_events_and_evidence() -> None:
    recovered = _behaviour_result("tool_failure_recovered")
    unrecovered = _behaviour_result("tool_failure_unrecovered")
    recovered_events = {event.event_type for event in _events(recovered)}
    unrecovered_events = {event.event_type for event in _events(unrecovered)}
    recovered_evidence = {
        (item.evidence_type.value, item.status.value)
        for item in recovered.behaviour_evidence_conversation_scope
    }
    unrecovered_evidence = {
        (item.evidence_type.value, item.status.value)
        for item in unrecovered.behaviour_evidence_conversation_scope
    }

    assert {"recovery_attempted", "recovery_succeeded"} <= recovered_events
    assert "recovery_failed" not in recovered_events
    assert "recovery_failed" in unrecovered_events
    assert recovered_evidence != unrecovered_evidence
    assert recovered.final_assessment.overall_status == AssessmentStatus.pass_with_warnings
    assert unrecovered.final_assessment.overall_status == AssessmentStatus.fail


def test_recovery_and_escalation_provenance_resolves_to_trace_events() -> None:
    for name in ("tool_failure_recovered", "tool_failure_unrecovered", "missing_escalation"):
        result = _behaviour_result(name)
        event_ids = {event.event_id for event in _events(result)}
        signal_ids = {
            signal.signal_id
            for behaviour_result in result.behaviour_results
            for signal in behaviour_result.business_signals
        }
        for behaviour_result in result.behaviour_results:
            for signal in behaviour_result.business_signals:
                assert set(signal.source_event_ids) <= event_ids
        for evidence in result.behaviour_evidence_conversation_scope:
            assert set(evidence.related_signals) <= signal_ids


def test_original_five_unified_decisions_are_unchanged() -> None:
    expected = {
        "mortgage_happy_path": AssessmentStatus.pass_,
        "investment_prompt_injection_handled": AssessmentStatus.pass_,
        "investment_guaranteed_return_policy_failure": AssessmentStatus.fail,
        "mortgage_hidden_eligibility_failure": AssessmentStatus.pass_with_warnings,
        "investment_suitability_failure": AssessmentStatus.fail,
    }

    assert {name: _run_scenario(name)[2].final_assessment.overall_status for name in list_scenarios()[:5]} == expected
