"""Convert raw TraceEvent objects from an ExecutionTrace into BusinessSignals.

Each mapping rule in this module corresponds to a rule entry in
``config/signal_rules.yaml``.  The two representations are kept in sync:
the YAML is the human-readable specification; this module is the executable
implementation.

Public API
----------
    extract_signals(trace: ExecutionTrace) -> list[BusinessSignal]
"""

from __future__ import annotations

from collections import Counter

from workshop_verify_agents.verification.signal_schema import (
    BusinessSignal,
    SignalSeverity,
    SignalType,
)
from workshop_verify_agents.verification.trace_schema import ExecutionTrace, TraceEvent


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_signals(trace: ExecutionTrace) -> list[BusinessSignal]:
    """Return all BusinessSignals derived from *trace*.

    Iterates over every TraceEvent and applies each extractor in order.
    A cross-event loop-risk check is applied after the per-event pass.
    """
    signals: list[BusinessSignal] = []

    for event in trace.events:
        signals.extend(_dispatch(event, trace.conversation_id))

    signals.extend(_check_loop_risk(trace))

    return signals


# ---------------------------------------------------------------------------
# Per-event dispatch
# ---------------------------------------------------------------------------

def _dispatch(event: TraceEvent, conversation_id: str) -> list[BusinessSignal]:
    """Route one TraceEvent to the appropriate extractor(s)."""
    handlers = {
        "safety_check_completed": _from_safety_check,
        "intent_classified":      _from_intent_classified,
        "route_selected":         _from_route_selected,
        "sub_agent_invoked":      _from_sub_agent_invoked,
        "response_written":       _from_response_written,
        "tool_call_failed":       _from_failed_execution,
        "sub_agent_failed":       _from_failed_execution,
    }
    handler = handlers.get(event.event_type)
    return handler(event, conversation_id) if handler else []


# ---------------------------------------------------------------------------
# Individual extractors
# ---------------------------------------------------------------------------

def _from_safety_check(event: TraceEvent, conversation_id: str) -> list[BusinessSignal]:
    """Rule RULE-S01 / RULE-S02: safety_check_completed → Safety signal."""
    action = event.metadata.get("action", "allow")
    passed = action == "allow"
    prompt_injection_detected = bool(event.metadata.get("prompt_injection_detected", False))
    safe_response_delivered = bool(event.metadata.get("safe_response_delivered", False))

    if passed and prompt_injection_detected and safe_response_delivered:
        explanation = (
            "Prompt-injection attempt detected; guardrail intervention completed and "
            "a safe response was delivered."
        )
    elif passed:
        explanation = "Safety layer cleared the request without intervention."
    else:
        explanation = (
            f"Safety layer blocked or flagged the request: "
            f"{event.metadata.get('reason', 'unknown')}."
        )

    return [BusinessSignal(
        conversation_id=conversation_id,
        turn_id=event.turn_id,
        signal_type=SignalType.safety,
        signal_name="safety_compliance" if passed else "safety_risk",
        value=action,
        severity=SignalSeverity.low if passed else SignalSeverity.critical,
        confidence=1.0,
        explanation=explanation,
        source_event_ids=[event.event_id],
    )]


def _from_intent_classified(event: TraceEvent, conversation_id: str) -> list[BusinessSignal]:
    """Rule RULE-R01: intent_classified → Routing signal."""
    domain = event.metadata.get("domain", "unknown")
    confidence: float = float(event.metadata.get("confidence", 0.0))

    # Low confidence warrants a higher severity to flag for review.
    if confidence >= 0.6:
        severity = SignalSeverity.low
    elif confidence >= 0.3:
        severity = SignalSeverity.medium
    else:
        severity = SignalSeverity.high

    return [BusinessSignal(
        conversation_id=conversation_id,
        turn_id=event.turn_id,
        signal_type=SignalType.routing,
        signal_name="intent_routing",
        value=domain,
        severity=severity,
        confidence=confidence,
        explanation=(
            f"Intent classified as '{domain}' with confidence {confidence:.0%}."
        ),
        source_event_ids=[event.event_id],
    )]


def _from_route_selected(event: TraceEvent, conversation_id: str) -> list[BusinessSignal]:
    """Rule RULE-J01: route_selected → Journey Routing signal."""
    domain = event.metadata.get("selected_domain", "unknown")

    return [BusinessSignal(
        conversation_id=conversation_id,
        turn_id=event.turn_id,
        signal_type=SignalType.journey,
        signal_name="journey_routing",
        value=domain,
        severity=SignalSeverity.low,
        confidence=1.0,
        explanation=f"Conversation routed to the '{domain}' domain agent.",
        source_event_ids=[event.event_id],
    )]


def _from_sub_agent_invoked(event: TraceEvent, conversation_id: str) -> list[BusinessSignal]:
    """Rule RULE-E01: sub_agent_invoked → Execution Path signal."""
    domain = event.metadata.get("domain", event.component_name)
    topic = event.metadata.get("topic", "unknown")

    return [BusinessSignal(
        conversation_id=conversation_id,
        turn_id=event.turn_id,
        signal_type=SignalType.execution,
        signal_name="execution_path",
        value=f"{domain}/{topic}",
        severity=SignalSeverity.low,
        confidence=1.0,
        explanation=f"Sub-agent '{domain}' invoked for topic '{topic}'.",
        source_event_ids=[event.event_id],
    )]


def _from_response_written(event: TraceEvent, conversation_id: str) -> list[BusinessSignal]:
    """Rule RULE-O01: response_written → Outcome Availability signal."""
    response_length: int = int(event.metadata.get("response_length", 0))
    # A very short response may indicate a truncation or fallback.
    severity = SignalSeverity.low if response_length >= 50 else SignalSeverity.medium

    return [BusinessSignal(
        conversation_id=conversation_id,
        turn_id=event.turn_id,
        signal_type=SignalType.outcome,
        signal_name="outcome_availability",
        value=response_length,
        severity=severity,
        confidence=1.0,
        explanation=(
            f"A response of {response_length} characters was delivered to the customer."
        ),
        source_event_ids=[event.event_id],
    )]


def _from_failed_execution(event: TraceEvent, conversation_id: str) -> list[BusinessSignal]:
    """Rule RULE-E02: tool_call_failed / sub_agent_failed → Execution Reliability Risk."""
    return [BusinessSignal(
        conversation_id=conversation_id,
        turn_id=event.turn_id,
        signal_type=SignalType.execution,
        signal_name="execution_reliability_risk",
        value=event.event_type,
        severity=SignalSeverity.high,
        confidence=1.0,
        explanation=(
            f"Component '{event.component_name}' reported a failure "
            f"(event_type='{event.event_type}'). "
            f"Details: {event.metadata.get('error', 'none provided')}."
        ),
        source_event_ids=[event.event_id],
    )]


# ---------------------------------------------------------------------------
# Cross-event checks
# ---------------------------------------------------------------------------

def _check_loop_risk(trace: ExecutionTrace) -> list[BusinessSignal]:
    """Rule RULE-L01: repeated route_selected / sub_agent_invoked → Loop Risk.

    If the same (event_type, component_name) pair occurs more than once within
    the same turn, it suggests unexpected repeated routing or planner loops.
    """
    signals: list[BusinessSignal] = []

    # Group by turn_id so we only flag within-turn repetitions.
    turns: dict[str, list[TraceEvent]] = {}
    for event in trace.events:
        turns.setdefault(event.turn_id, []).append(event)

    loop_event_types = {"route_selected", "sub_agent_invoked"}

    for turn_id, events in turns.items():
        counts = Counter(
            (e.event_type, e.component_name)
            for e in events
            if e.event_type in loop_event_types
        )
        for (event_type, component), count in counts.items():
            if count > 1:
                source_ids = [
                    e.event_id for e in events
                    if e.event_type == event_type and e.component_name == component
                ]
                signals.append(BusinessSignal(
                    conversation_id=trace.conversation_id,
                    turn_id=turn_id,
                    signal_type=SignalType.operational,
                    signal_name="loop_risk",
                    value=count,
                    severity=SignalSeverity.high,
                    confidence=0.9,
                    explanation=(
                        f"'{event_type}' from '{component}' fired {count} times "
                        f"within a single turn — possible routing loop."
                    ),
                    source_event_ids=source_ids,
                ))

    return signals
