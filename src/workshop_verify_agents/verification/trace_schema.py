"""Pydantic schemas for raw agent execution traces.

Framework-agnostic: events may originate from ADK callbacks, LangChain
tracing, custom middleware, or synthetic test fixtures.  All agent-side
code should emit ``TraceEvent`` objects rather than framework-specific
structures so that the verification pipeline stays portable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TraceEvent(BaseModel):
    """A single atomic event emitted by one component of the agent system.

    Events are the lowest-level unit of observability.  Every tool call,
    LLM invocation, sub-agent handoff, safety intervention, or routing
    decision should produce exactly one TraceEvent.
    """

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    """Unique identifier for this event."""

    conversation_id: str
    """Identifies the end-to-end conversation session this event belongs to."""

    turn_id: str
    """Identifies the specific conversational turn within the session."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    """UTC wall-clock time when the event was emitted."""

    component_name: str
    """Name of the agent component that produced this event.

    Examples: ``'orchestrator'``, ``'mortgage_agent'``, ``'safety_layer'``,
    ``'intent_classifier'``.
    """

    event_type: str
    """Machine-readable event category.

    Matches the ``event_type`` values referenced in ``signal_rules.yaml``.
    Examples: ``'tool_call'``, ``'llm_response'``, ``'sub_agent_handoff'``,
    ``'safety_layer_triggered'``, ``'intent_classified'``.
    """

    input_summary: str | None = None
    """Optional human-readable summary of the input that triggered this event."""

    output_summary: str | None = None
    """Optional human-readable summary of the output or result of this event."""

    metadata: dict[str, Any] = Field(default_factory=dict)
    """Free-form payload carrying event-specific details.

    The SignalExtractor evaluates rule conditions against this dict, so keys
    should be stable and documented in ``signal_rules.yaml``.
    Examples: ``{'tool_name': 'run_affordability_check'}``,
    ``{'grounding_score': 0.42}``, ``{'action': 'block'}``.
    """


class ExecutionTrace(BaseModel):
    """Ordered sequence of TraceEvents for a single conversation session.

    Collect all events produced during a conversation, then pass the
    ``ExecutionTrace`` to the verification pipeline for signal extraction.
    """

    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    """Unique identifier for this trace."""

    conversation_id: str
    """Must match the ``conversation_id`` on every contained TraceEvent."""

    events: list[TraceEvent] = Field(default_factory=list)
    """Chronologically ordered list of events; maintained in insertion order."""

    def add_event(self, event: TraceEvent) -> None:
        """Append an event to the trace."""
        self.events.append(event)

    def filter_by_component(self, component_name: str) -> list[TraceEvent]:
        """Return all events emitted by the named component."""
        return [e for e in self.events if e.component_name == component_name]

    def filter_by_event_type(self, event_type: str) -> list[TraceEvent]:
        """Return all events whose event_type matches the given value."""
        return [e for e in self.events if e.event_type == event_type]
