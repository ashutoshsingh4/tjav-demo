import json

from workshop_verify_agents.assurance_interpretation import (
    _table_rows,
    generate_outputs,
    interpret_scenario,
    vocabulary,
)
from workshop_verify_agents.examples.conversations import list_scenarios


def test_vocabulary_entries_have_supported_source_types_and_rules() -> None:
    supported = {
        "observed trace event",
        "derived signal",
        "configured control interpretation",
        "supplied journey outcome",
        "derived trace absence",
    }

    assert vocabulary()
    assert all(entry.source_type in supported for entry in vocabulary())
    assert all(entry.identifier and entry.extraction_rule for entry in vocabulary())


def test_observed_behaviours_have_trace_provenance() -> None:
    report = interpret_scenario("tool_failure_recovered")

    assert report.observed_behaviours
    assert all(item["provenance"] for item in report.observed_behaviours)
    assert any(item["category"] == "TOOL_CALL_FAILED" for item in report.observed_behaviours)


def test_recovery_interpretations_have_derived_signal_and_event_provenance() -> None:
    report = interpret_scenario("tool_failure_recovered")
    categories = {item["category"] for item in report.derived_behaviours}
    recovery_observations = {
        item["category"]: item["provenance"]
        for item in report.observed_behaviours
        if item["category"] in {"RECOVERY_ATTEMPTED", "RECOVERY_SUCCEEDED"}
    }

    assert {"RECOVERY_ATTEMPTED", "RECOVERY_SUCCEEDED"} <= categories
    assert all(item["provenance"] for item in report.derived_behaviours)
    assert all("event-004" in references for references in recovery_observations.values())


def test_recovered_and_unrecovered_reports_are_distinct() -> None:
    recovered = interpret_scenario("tool_failure_recovered")
    unrecovered = interpret_scenario("tool_failure_unrecovered")

    assert recovered.unified_decision != unrecovered.unified_decision
    assert "RECOVERY_SUCCEEDED" in {item["category"] for item in recovered.observed_behaviours}
    assert "RECOVERY_FAILED" in {item["category"] for item in unrecovered.observed_behaviours}


def test_prompt_injection_control_interpretations_differ() -> None:
    handled = interpret_scenario("investment_prompt_injection_handled")
    unhandled = interpret_scenario("unhandled_prompt_injection")

    assert handled.control_results[0]["control_effective"] is True
    assert unhandled.control_results[0]["control_effective"] is False
    assert handled.unified_decision != unhandled.unified_decision


def test_missing_escalation_reports_requirement_and_omission() -> None:
    report = interpret_scenario("missing_escalation")
    observed_categories = {item["category"] for item in report.observed_behaviours}

    assert {"ESCALATION_REQUIRED", "ESCALATION_OMITTED"} <= observed_categories
    assert report.control_results[-1]["policy_type"] == "escalation_control"
    assert report.control_results[-1]["status"] == "fail"


def test_baseline_disagreements_are_derived_from_baseline_ratings() -> None:
    report = interpret_scenario("critical_stage_hidden_weakness")
    baselines = report.outcome_findings["baselines"]

    assert baselines["flat_mean"]["rating"] == "PASS"
    assert baselines["journey_weighted"]["rating"] == "FAIL"
    assert any("flat_mean=PASS" in item for item in report.baseline_disagreements)


def test_reports_distinguish_supplied_inputs_from_observed_behaviour() -> None:
    report = interpret_scenario("outcome_fail_behaviour_pass")

    assert report.supplied_inputs["quality_scores"] == [0.4]
    assert report.supplied_inputs["stage_labels"] == ["recommendation_or_guidance"]
    assert all("quality_score" not in item.get("details", {}) for item in report.observed_behaviours)


def test_generated_outputs_are_deterministic_and_complete(tmp_path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    generate_outputs(first)
    generate_outputs(second)

    first_json = first / "tool_failure_recovered" / "interpretation.json"
    second_json = second / "tool_failure_recovered" / "interpretation.json"
    assert json.loads(first_json.read_text(encoding="utf-8")) == json.loads(second_json.read_text(encoding="utf-8"))
    assert (first / "PAPER_UPDATE_NOTES.md").exists()
    assert (first / "tables" / "table_1_baseline_ablation.csv").exists()
    assert (first / "tables" / "table_4_scenario_support.tex").exists()


def test_tables_are_generated_from_interpretation_reports() -> None:
    reports = [interpret_scenario(name) for name in ("mortgage_happy_path", "critical_stage_hidden_weakness")]
    tables = _table_rows(reports)

    assert tables["table_1_baseline_ablation"][1]["unified"] == "fail"
    assert tables["table_2_behaviour_coverage"][1]["provenance_valid"] == "true"
    assert tables["table_3_controlled_contrasts"]
    assert tables["table_4_scenario_support"]


def test_scenario_support_placement_matches_paper_allocation() -> None:
    reports = [interpret_scenario(name) for name in list_scenarios()]
    support_rows = _table_rows(reports)["table_4_scenario_support"]
    main_paper_scenarios = {
        row["scenario"]
        for row in support_rows
        if row["suitable_for"] == "main-paper exemplar"
    }

    assert main_paper_scenarios == {
        "mortgage_happy_path",
        "investment_prompt_injection_handled",
        "outcome_pass_behaviour_fail",
        "critical_stage_hidden_weakness",
        "tool_failure_recovered",
        "tool_failure_unrecovered",
        "missing_escalation",
        "outcome_fail_behaviour_pass",
    }
