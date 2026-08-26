"""Small offline demo for conversation-level unified verification."""

from __future__ import annotations

import textwrap
from typing import Any

from workshop_verify_agents.examples.conversations import get_exchanges, get_scenario
from workshop_verify_agents.journey.journey_taxonomy import stage_weight
from workshop_verify_agents.verification.evidence_schema import VerificationEvidence
from workshop_verify_agents.verification.offline_verifier import (
    verify_completed_conversation,
)
from workshop_verify_agents.verification.online_verifier import verify_turn_behaviour
from workshop_verify_agents.verification.trace_schema import ExecutionTrace, TraceEvent


def _build_demo_trace_for_turn(
    conversation_id: str,
    turn_index: int,
    role: str,
    text: str,
    journey_stage: str,
    turn_metadata: dict[str, Any] | None = None,
) -> ExecutionTrace:
    turn_metadata = turn_metadata or {}
    turn_id = f"turn-{turn_index}"
    selected_domain = turn_metadata.get("routing_domain") or (
        "mortgage"
        if journey_stage in {"eligibility_or_suitability", "recommendation_or_guidance"}
        else "general"
    )
    safety_metadata = {
        "action": "allow",
        "reason": "offline-demo",
    }
    if turn_metadata.get("prompt_injection_attempt"):
        safety_metadata.update({
            "prompt_injection_detected": True,
            "guardrail_action": turn_metadata.get("guardrail_action", "safe_response"),
            "safe_response_delivered": bool(turn_metadata.get("safe_response_delivered", False)),
            "instructions_leaked": bool(turn_metadata.get("instructions_leaked", False)),
            "redirection_present": bool(turn_metadata.get("redirection_present", False)),
        })
    if turn_metadata.get("guaranteed_return_request"):
        safety_metadata.update({
            "guaranteed_return_request": True,
        })
    trace = ExecutionTrace(conversation_id=conversation_id)
    trace.add_event(TraceEvent(
        conversation_id=conversation_id,
        turn_id=turn_id,
        component_name="safety_layer",
        event_type="safety_check_completed",
        metadata=safety_metadata,
        input_summary=f"role={role} text={text[:80]}",
        output_summary=f"action={safety_metadata['action']}",
    ))
    trace.add_event(TraceEvent(
        conversation_id=conversation_id,
        turn_id=turn_id,
        component_name="intent_classifier",
        event_type="intent_classified",
        metadata={"domain": selected_domain, "confidence": 0.82},
        output_summary=f"domain={selected_domain} confidence=0.82",
    ))
    trace.add_event(TraceEvent(
        conversation_id=conversation_id,
        turn_id=turn_id,
        component_name="orchestrator",
        event_type="route_selected",
        metadata={"selected_domain": selected_domain},
        output_summary=f"domain={selected_domain}",
    ))
    if turn_metadata.get("behaviour_issue") == "routing_loop":
        trace.add_event(TraceEvent(
            conversation_id=conversation_id,
            turn_id=turn_id,
            component_name="orchestrator",
            event_type="route_selected",
            metadata={"selected_domain": selected_domain},
            output_summary=f"domain={selected_domain}",
        ))
    trace.add_event(TraceEvent(
        conversation_id=conversation_id,
        turn_id=turn_id,
        component_name=f"{selected_domain}_agent",
        event_type="sub_agent_invoked",
        metadata={"domain": selected_domain, "topic": journey_stage},
        output_summary="topic=guidance",
    ))
    if turn_metadata.get("behaviour_issue") == "routing_loop":
        trace.add_event(TraceEvent(
            conversation_id=conversation_id,
            turn_id=turn_id,
            component_name=f"{selected_domain}_agent",
            event_type="sub_agent_invoked",
            metadata={"domain": selected_domain, "topic": journey_stage},
            output_summary="topic=guidance",
        ))
    response_metadata = {"response_length": len(text)}
    for key in (
        "guarantee_language_present",
        "disclaimer_present",
        "uncertainty_statement_present",
    ):
        if key in turn_metadata:
            response_metadata[key] = bool(turn_metadata[key])
    trace.add_event(TraceEvent(
        conversation_id=conversation_id,
        turn_id=turn_id,
        component_name="response_writer",
        event_type="response_written",
        metadata=response_metadata,
        output_summary=f"response_length={len(text)}",
    ))
    return trace


def _build_demo_trace_for_exchange(
    conversation_id: str,
    exchange_index: int,
    user_turn: dict[str, Any],
    agent_turn: dict[str, Any],
    journey_stage: str,
) -> ExecutionTrace:
    """Build one trace for a user query and its corresponding agent response."""
    metadata = {**user_turn, **agent_turn}
    return _build_demo_trace_for_turn(
        conversation_id=conversation_id,
        turn_index=exchange_index,
        role="user_agent_exchange",
        text=str(agent_turn.get("text", "")),
        journey_stage=journey_stage,
        turn_metadata=metadata,
    )


def _preview(text: str, width: int = 58) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= width:
        return compact
    return compact[: width - 3] + "..."


def _print_table(title: str, headers: list[str], rows: list[list[object]]) -> None:
    print(f"\n{title}")
    if not rows:
        print("  (none)")
        return

    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    def _fmt(row: list[object]) -> str:
        return "  " + " | ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row))

    print(_fmt(headers))
    print("  " + "-+-".join("-" * w for w in widths))
    for row in rows:
        print(_fmt(row))


def _print_evidence(title: str, items: list[VerificationEvidence]) -> None:
    print(f"\n{title}")
    if not items:
        print("  (none)")
        return
    for item in items:
        print(f"  - {item.evidence_type.value}: {item.status.value}")
        if item.explanation:
            wrapped = textwrap.wrap(item.explanation, width=86)
            if wrapped:
                print(f"    {wrapped[0]}")


def demo_offline_verification(
    scenario_name: str = "mortgage_hidden_eligibility_failure",
) -> None:
    """Run one small offline conversation-level verification demo."""
    scenario = get_scenario(scenario_name)
    turns = list(scenario.get("turns", []))
    exchanges = get_exchanges(scenario)
    stages = [str(exchange["journey_stage"]) for exchange in exchanges]
    scores = [float(exchange["quality_score"]) for exchange in exchanges]
    conversation_id = f"offline::{scenario_name}"

    behaviour_results = []
    for index, exchange in enumerate(exchanges):
        user_turn = turns[index * 2]
        agent_turn = turns[index * 2 + 1]
        trace = _build_demo_trace_for_exchange(
            conversation_id=conversation_id,
            exchange_index=index,
            user_turn=user_turn,
            agent_turn=agent_turn,
            journey_stage=str(exchange["journey_stage"]),
        )
        behaviour_results.append(
            verify_turn_behaviour(
                conversation_id=conversation_id,
                turn_index=index,
                execution_trace=trace,
            )
        )

    unified = verify_completed_conversation(
        conversation_id=conversation_id,
        behaviour_results=behaviour_results,
        conversation_turns=turns,
        turn_scores=scores,
        journey_stage_labels=stages,
        conversation_exchanges=exchanges,
    )

    print(f"Scenario: {scenario_name}")

    turn_rows = []
    for idx, exchange in enumerate(exchanges):
        role = "exchange"
        text = str(exchange.get("agent_response", ""))
        stage = str(exchange["journey_stage"])
        score = float(exchange["quality_score"])
        weight = stage_weight(stage) if stage != "unknown" else "n/a"
        turn_rows.append([
            idx,
            role,
            _preview(text),
            stage,
            f"{float(score):.2f}" if isinstance(score, (int, float)) else score,
            f"{float(weight):.2f}" if isinstance(weight, (int, float)) else weight,
        ])
    _print_table(
        "Conversation Turns",
        ["turn_index", "role", "text_preview", "journey_stage", "quality_score", "stage_weight"],
        turn_rows,
    )

    behaviour_rows = []
    for result in behaviour_results:
        behaviour_rows.append([
            result.turn_index,
            len(result.execution_trace.events),
            len(result.business_signals),
            result.behaviour_assessment.overall_status.value,
        ])
    _print_table(
        "Per-turn Behaviour Summary",
        ["turn_index", "trace_event_count", "signal_count", "behaviour_status"],
        behaviour_rows,
    )

    _print_evidence("Behaviour Evidence (conversation scope)", unified.behaviour_evidence_conversation_scope)
    _print_evidence(
        "Outcome Evidence (conversation scope)",
        unified.outcome_result.outcome_evidence if unified.outcome_result else [],
    )

    outcome_summary = unified.outcome_result.journey_aware_result if unified.outcome_result else {}
    if outcome_summary:
        simple_rating = str(outcome_summary.get("simple_rating", "n/a"))
        weighted_rating = str(outcome_summary.get("journey_weighted_rating", "n/a"))
        critical_failures = outcome_summary.get("critical_stage_failures", [])
        rating_changed = simple_rating != weighted_rating
        print("\nConversation-level Outcome Summary")
        print(f"  - simple_average_score: {outcome_summary.get('simple_average', 'n/a')}")
        print(f"  - journey_weighted_score: {outcome_summary.get('journey_weighted_score', 'n/a')}")
        print(f"  - simple_rating: {simple_rating}")
        print(f"  - journey_weighted_rating: {weighted_rating}")
        print(f"  - rating_changed: {rating_changed}")
        print(f"  - critical_stage_failures: {critical_failures}")

    print("\nFinal Unified Assessment")
    print(f"  - completeness: {unified.completeness}")
    print(f"  - overall_status: {unified.final_assessment.overall_status.value}")
    if unified.final_assessment.summary:
        print(f"  - summary: {unified.final_assessment.summary}")
    if unified.warnings:
        for warning in unified.warnings:
            print(f"  - warning: {warning}")


if __name__ == "__main__":
    demo_offline_verification()
