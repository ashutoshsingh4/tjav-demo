"""Root orchestrator agent for the workshop verification demo.

Wires together the safety layer, intent classifier, domain sub-agents, and
response writer into a single ``run()`` function.  Every important stage
emits a ``TraceEvent`` so the downstream verification pipeline has a full
audit record.

Pipeline per turn
-----------------
1. safety_layer.check()       → safety_check_started / safety_check_completed
2. intent_classifier.classify() → intent_classified
3. _route()                   → route_selected
4. <domain>.handle()          → sub_agent_invoked
5. response_writer.write()    → response_written

Returns a ``TurnResult`` containing the final response text and the populated
``ExecutionTrace`` for the full conversation turn.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from workshop_verify_agents.synthetic_runtime import intent_classifier, response_writer, safety_layer
from workshop_verify_agents.synthetic_runtime.sub_agents import (
    investment_agent,
    mortgage_agent,
    pension_agent,
)
from workshop_verify_agents.verification.trace_schema import ExecutionTrace, TraceEvent


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class TurnResult:
    """Output of a single orchestrated conversation turn."""

    final_response: str
    """The customer-facing response after safety checks and formatting."""

    execution_trace: ExecutionTrace
    """All TraceEvents emitted during this turn, in chronological order."""

    blocked: bool = False
    """True if the safety layer blocked the request before any sub-agent ran."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run(
    user_input: str,
    conversation_id: str | None = None,
    turn_id: str | None = None,
) -> TurnResult:
    """Process one conversation turn end-to-end.

    Parameters
    ----------
    user_input:
        The raw customer utterance.
    conversation_id:
        Identifier for the ongoing conversation session.  A new UUID is
        generated if not provided.
    turn_id:
        Identifier for this specific turn.  A new UUID is generated if not
        provided.

    Returns
    -------
    TurnResult
        Contains the final response text and the full execution trace.
    """
    conversation_id = conversation_id or str(uuid4())
    turn_id = turn_id or str(uuid4())

    trace = ExecutionTrace(conversation_id=conversation_id)

    # ------------------------------------------------------------------
    # Step 1 — Safety check
    # ------------------------------------------------------------------
    safety_result = safety_layer.check(user_input, conversation_id, turn_id, trace)

    if not safety_result.safe:
        return TurnResult(
            final_response=safety_result.sanitised_input,
            execution_trace=trace,
            blocked=True,
        )

    # ------------------------------------------------------------------
    # Step 2 — Intent classification
    # ------------------------------------------------------------------
    intent_result = intent_classifier.classify(user_input, conversation_id, turn_id, trace)

    # ------------------------------------------------------------------
    # Step 3 — Routing
    # ------------------------------------------------------------------
    domain = intent_result.domain
    _emit_route_selected(domain, conversation_id, turn_id, trace)

    # ------------------------------------------------------------------
    # Step 4 — Sub-agent dispatch
    # ------------------------------------------------------------------
    draft = _dispatch(domain, user_input, conversation_id, turn_id, trace)

    # ------------------------------------------------------------------
    # Step 5 — Response writing
    # ------------------------------------------------------------------
    final_response = response_writer.write(draft, domain, conversation_id, turn_id, trace)

    return TurnResult(final_response=final_response, execution_trace=trace)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _emit_route_selected(
    domain: str,
    conversation_id: str,
    turn_id: str,
    trace: ExecutionTrace,
) -> None:
    """Emit a route_selected TraceEvent."""
    trace.add_event(TraceEvent(
        conversation_id=conversation_id,
        turn_id=turn_id,
        component_name="orchestrator",
        event_type="route_selected",
        output_summary=f"domain={domain}",
        metadata={"selected_domain": domain},
    ))


def _dispatch(
    domain: str,
    user_input: str,
    conversation_id: str,
    turn_id: str,
    trace: ExecutionTrace,
) -> str:
    """Route to the correct domain sub-agent and return its draft response."""
    if domain == "mortgage":
        return mortgage_agent.handle(user_input, conversation_id, turn_id, trace)
    if domain == "investment":
        return investment_agent.handle(user_input, conversation_id, turn_id, trace)
    if domain == "pension":
        return pension_agent.handle(user_input, conversation_id, turn_id, trace)

    # Fallback: general query — synthesise a brief signposting response
    trace.add_event(TraceEvent(
        conversation_id=conversation_id,
        turn_id=turn_id,
        component_name="orchestrator",
        event_type="sub_agent_invoked",
        input_summary=user_input[:120],
        output_summary="domain=general (fallback)",
        metadata={"domain": "general"},
    ))
    return (
        "I can help you with questions about mortgages, investments, and pensions. "
        "Could you tell me more about what you're looking for?"
    )
