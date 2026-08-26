"""Normalises ADK runtime events into the generic ExecutionTrace schema.

Framework contract
------------------
The custom orchestrator in ``root_agent.py`` emits semantic ``Event`` objects
whose ``content.parts[0].text`` is a JSON-encoded payload carrying metadata
(action, domain, confidence, etc.). This adapter parses those payloads and
maps each event's ``author`` name to the canonical ``event_type`` values
expected by the downstream signal extractor.

Important clarification
------------------------
The root orchestrator is a manual workflow controller, not a native ADK
sub-agent delegation tree. The final response is emitted by the root agent
itself and should be treated as a delivery event, not as a sub-agent invocation.

Defensive design
----------------
All extraction is wrapped in try/except blocks because:
    - ADK event objects vary across versions.
    - Content may be a ``types.Content`` object or a plain dict.
    - Event text may be plain prose rather than JSON (e.g. third-party events).
    - Some fields (timestamp, invocation_id) may be absent.

Public API
----------
        normalise_adk_events_to_execution_trace(events, conversation_id) -> ExecutionTrace
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from workshop_verify_agents.verification.trace_schema import ExecutionTrace, TraceEvent


# ---------------------------------------------------------------------------
# Author → semantic event_type mapping
# ---------------------------------------------------------------------------

_AUTHOR_TO_EVENT_TYPE: dict[str, str] = {
    "safety_check_started":  "safety_check_started",
    "safety_agent":          "safety_check_completed",
    "intent_router_agent":   "intent_classified",
    "route_selector":        "route_selected",
    # Domain agents — matched by suffix in _resolve_event_type()
    "mortgage_agent":        "sub_agent_invoked",
    "investment_agent":      "sub_agent_invoked",
    "pension_agent":         "sub_agent_invoked",
    "general_agent":         "sub_agent_invoked",
    "response_writer_agent": "response_written",
    "finance_verification_agent": "final_response_delivered",
    # ADK internal / unknown
    "user":                  "user_message",
}

# Authors whose events carry only the final response text (not metadata)
_FINAL_RESPONSE_AUTHORS = {"finance_verification_agent"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalise_adk_events_to_execution_trace(
    adk_events: list[Any],
    conversation_id: str,
) -> ExecutionTrace:
    """Convert a list of ADK ``Event`` objects to a generic ``ExecutionTrace``.

    Events from the orchestrator that contain JSON payloads are parsed for
    metadata.  All other events are included with best-effort extraction.
    User-message events (author='user') are skipped as they are not
    verification-relevant.
    """
    trace = ExecutionTrace(conversation_id=conversation_id)

    for raw_event in adk_events:
        trace_event = _convert_event(raw_event, conversation_id)
        if trace_event is not None:
            trace.add_event(trace_event)

    return trace


# ---------------------------------------------------------------------------
# Single-event conversion
# ---------------------------------------------------------------------------

def _convert_event(raw_event: Any, conversation_id: str) -> TraceEvent | None:
    """Convert one ADK event to a TraceEvent, or return None to skip it."""
    author = _safe_str(getattr(raw_event, "author", None)) or "unknown"

    # Skip user-input events
    if author in ("user", ""):
        return None

    invocation_id = _safe_str(getattr(raw_event, "invocation_id", None)) or conversation_id
    event_type = _resolve_event_type(author)
    timestamp = _extract_timestamp(raw_event)
    text = _extract_text(raw_event)

    # Try to parse JSON payload from the event text
    payload = _try_parse_json(text)

    input_summary, output_summary, metadata = _extract_semantic_fields(
        author, event_type, text, payload
    )

    return TraceEvent(
        conversation_id=conversation_id,
        turn_id=invocation_id,
        timestamp=timestamp,
        component_name=author,
        event_type=event_type,
        input_summary=input_summary,
        output_summary=output_summary,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Field extractors
# ---------------------------------------------------------------------------

def _resolve_event_type(author: str) -> str:
    """Map an author name to a canonical event_type.

    Performs an exact lookup first; falls back to suffix matching for
    domain agents (e.g. ``'mortgage_agent'``) that share the same type.
    """
    if author in _AUTHOR_TO_EVENT_TYPE:
        return _AUTHOR_TO_EVENT_TYPE[author]
    if author == "finance_verification_agent":
        return "final_response_delivered"
    if author.endswith("_agent"):
        return "sub_agent_invoked"
    return "agent_event"


def _extract_text(raw_event: Any) -> str:
    """Safely extract the text content from an ADK Event."""
    try:
        content = getattr(raw_event, "content", None)
        if content is None:
            return ""

        # types.Content with .parts attribute
        if hasattr(content, "parts"):
            parts = content.parts or []
            for part in parts:
                text = getattr(part, "text", None)
                if text:
                    return str(text)

        # Dict-style content {"parts": [{"text": "..."}]}
        if isinstance(content, dict):
            for part in content.get("parts", []):
                if isinstance(part, dict):
                    text = part.get("text")
                    if text:
                        return str(text)
    except Exception:
        pass
    return ""


def _extract_timestamp(raw_event: Any) -> datetime:
    """Extract a UTC timestamp from the event, falling back to now()."""
    try:
        ts = getattr(raw_event, "timestamp", None)
        if ts is None:
            return datetime.now(timezone.utc)
        if isinstance(ts, datetime):
            return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        # Some ADK versions expose timestamp as a float (Unix epoch)
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(float(ts), tz=timezone.utc)
    except Exception:
        pass
    return datetime.now(timezone.utc)


def _try_parse_json(text: str) -> dict[str, Any] | None:
    """Try to parse *text* as JSON; return None on failure."""
    if not text or not text.strip().startswith("{"):
        return None
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None


def _extract_semantic_fields(
    author: str,
    event_type: str,
    raw_text: str,
    payload: dict[str, Any] | None,
) -> tuple[str | None, str | None, dict[str, Any]]:
    """Produce (input_summary, output_summary, metadata) from available fields."""
    metadata: dict[str, Any] = {}
    input_summary: str | None = None
    output_summary: str | None = None

    if payload:
        metadata = {k: v for k, v in payload.items()}

        # Derive human-readable summaries from well-known payload keys
        if event_type == "safety_check_completed":
            action = payload.get("action", "unknown")
            reason = payload.get("reason", "")
            output_summary = f"action={action}" + (f" — {reason}" if reason else "")

        elif event_type == "intent_classified":
            domain = payload.get("domain", "unknown")
            confidence = payload.get("confidence", 0.0)
            output_summary = f"domain={domain} confidence={float(confidence):.2f}"

        elif event_type == "route_selected":
            output_summary = f"domain={payload.get('selected_domain', 'unknown')}"

        elif event_type == "sub_agent_invoked":
            domain = payload.get("domain", author.replace("_agent", ""))
            output_summary = f"domain={domain} draft_length={payload.get('draft_length', '?')}"

        elif event_type == "response_written":
            output_summary = f"response_length={payload.get('response_length', '?')}"

        elif event_type == "final_response_delivered":
            output_summary = raw_text[:120] if raw_text else "final response delivered"

        elif event_type == "safety_check_started":
            input_summary = payload.get("summary")

    elif raw_text:
        # Non-JSON event (e.g. final response or third-party event)
        if event_type == "final_response_delivered":
            output_summary = raw_text[:120]
        else:
            output_summary = raw_text[:120] if raw_text else None

    return input_summary, output_summary, metadata


# ---------------------------------------------------------------------------
# Safe string coercion
# ---------------------------------------------------------------------------

def _safe_str(value: Any) -> str:
    try:
        return str(value) if value is not None else ""
    except Exception:
        return ""
