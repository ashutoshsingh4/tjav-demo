"""Golden ADK event fixtures for adk_trace_adapter unit tests.

Each entry in GOLDEN_EVENT_SCENARIOS defines one input FakeAdkEvent and the
exact TraceEvent fields that adk_trace_adapter should produce from it.

Dynamic fields (event_id, signal_id, timestamp where no fixture value is set)
are excluded from assertions; tests should assert only on the fields listed in
each scenario's ``expected_*`` keys.

These fixtures document the stable author→event_type mapping and metadata
extraction contract of the adapter. Any change to the mapping must update
these golden expectations.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


_FIXED_TIMESTAMP = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
_DEFAULT_INVOCATION_ID = "inv-golden-001"
_FIXED_UNIX_TS = 1751371200.0  # 2025-07-01 12:00:00 UTC


# ---------------------------------------------------------------------------
# Minimal stand-ins for google.adk Event objects
# ---------------------------------------------------------------------------


@dataclass
class FakePart:
    text: str


@dataclass
class FakeAdkContent:
    parts: list[FakePart]


@dataclass
class FakeAdkEvent:
    """Minimal stand-in for a google.adk Event.

    The adapter accesses only `author`, `content`, `invocation_id`, and
    `timestamp` via getattr, so this dataclass satisfies the contract.
    """

    author: str
    content: FakeAdkContent | None = None
    invocation_id: str = _DEFAULT_INVOCATION_ID
    timestamp: Any = field(default_factory=lambda: _FIXED_TIMESTAMP)


# ---------------------------------------------------------------------------
# Event factory helpers
# ---------------------------------------------------------------------------


def make_json_event(
    author: str,
    payload: dict[str, Any],
    invocation_id: str = _DEFAULT_INVOCATION_ID,
) -> FakeAdkEvent:
    """Return a FakeAdkEvent whose content text is a JSON-encoded payload dict."""
    return FakeAdkEvent(
        author=author,
        content=FakeAdkContent(parts=[FakePart(text=json.dumps(payload))]),
        invocation_id=invocation_id,
    )


def make_text_event(
    author: str,
    text: str,
    invocation_id: str = _DEFAULT_INVOCATION_ID,
) -> FakeAdkEvent:
    """Return a FakeAdkEvent with plain (non-JSON) text content."""
    return FakeAdkEvent(
        author=author,
        content=FakeAdkContent(parts=[FakePart(text=text)]),
        invocation_id=invocation_id,
    )


def make_empty_event(
    author: str,
    invocation_id: str = _DEFAULT_INVOCATION_ID,
) -> FakeAdkEvent:
    """Return a FakeAdkEvent with no content (edge-case guard)."""
    return FakeAdkEvent(author=author, content=None, invocation_id=invocation_id)


# ---------------------------------------------------------------------------
# Golden event scenarios
# ---------------------------------------------------------------------------
# Each scenario:
#   name                       unique identifier for parametrise / pytest id
#   description                one-line explanation
#   event                      FakeAdkEvent input
#   expect_none                True → adapter must return None (event skipped)
#   expected_event_type        canonical event_type value expected on TraceEvent
#   expected_component_name    component_name value expected on TraceEvent
#   expected_metadata_subset   dict of key/value pairs that must appear in metadata
#   expected_output_summary    exact output_summary string (optional; omit to skip)
# ---------------------------------------------------------------------------

GOLDEN_EVENT_SCENARIOS: list[dict[str, Any]] = [
    # ── Skipped events ──────────────────────────────────────────────────────
    {
        "name": "user_event_skipped",
        "description": "User-authored events are filtered and must not appear in the trace.",
        "event": make_text_event("user", "Hello, I need help."),
        "expect_none": True,
    },
    {
        "name": "empty_author_becomes_unknown",
        "description": "An empty author is coerced to 'unknown' by _safe_str; event is kept as agent_event.",
        "event": FakeAdkEvent(author="", content=None),
        "expect_none": False,
        "expected_event_type": "agent_event",
        "expected_component_name": "unknown",
        "expected_metadata_subset": {},
    },
    # ── Safety events ────────────────────────────────────────────────────────
    {
        "name": "safety_allow",
        "description": "safety_agent allow → safety_check_completed with action=allow metadata.",
        "event": make_json_event("safety_agent", {"action": "allow", "reason": "clean"}),
        "expect_none": False,
        "expected_event_type": "safety_check_completed",
        "expected_component_name": "safety_agent",
        "expected_metadata_subset": {"action": "allow", "reason": "clean"},
        "expected_output_summary": "action=allow — clean",
    },
    {
        "name": "safety_prompt_injection",
        "description": "Prompt-injection detected with safe response flows through metadata.",
        "event": make_json_event(
            "safety_agent",
            {
                "action": "allow",
                "prompt_injection_detected": True,
                "safe_response_delivered": True,
                "instructions_leaked": False,
                "redirection_present": True,
            },
        ),
        "expect_none": False,
        "expected_event_type": "safety_check_completed",
        "expected_component_name": "safety_agent",
        "expected_metadata_subset": {
            "action": "allow",
            "prompt_injection_detected": True,
            "safe_response_delivered": True,
        },
    },
    {
        "name": "safety_allow_no_reason",
        "description": "safety_agent allow without a reason field still maps correctly.",
        "event": make_json_event("safety_agent", {"action": "allow"}),
        "expect_none": False,
        "expected_event_type": "safety_check_completed",
        "expected_component_name": "safety_agent",
        "expected_metadata_subset": {"action": "allow"},
        "expected_output_summary": "action=allow",
    },
    # ── Routing events ───────────────────────────────────────────────────────
    {
        "name": "intent_classified_mortgage",
        "description": "intent_router_agent → intent_classified with domain and confidence.",
        "event": make_json_event(
            "intent_router_agent",
            {"domain": "mortgage", "confidence": 0.85},
        ),
        "expect_none": False,
        "expected_event_type": "intent_classified",
        "expected_component_name": "intent_router_agent",
        "expected_metadata_subset": {"domain": "mortgage", "confidence": 0.85},
        "expected_output_summary": "domain=mortgage confidence=0.85",
    },
    {
        "name": "route_selected_investment",
        "description": "route_selector → route_selected with selected_domain.",
        "event": make_json_event("route_selector", {"selected_domain": "investment"}),
        "expect_none": False,
        "expected_event_type": "route_selected",
        "expected_component_name": "route_selector",
        "expected_metadata_subset": {"selected_domain": "investment"},
        "expected_output_summary": "domain=investment",
    },
    # ── Domain-agent events ──────────────────────────────────────────────────
    {
        "name": "sub_agent_mortgage",
        "description": "mortgage_agent → sub_agent_invoked.",
        "event": make_json_event("mortgage_agent", {"domain": "mortgage", "draft_length": 150}),
        "expect_none": False,
        "expected_event_type": "sub_agent_invoked",
        "expected_component_name": "mortgage_agent",
        "expected_metadata_subset": {"domain": "mortgage", "draft_length": 150},
    },
    {
        "name": "sub_agent_investment",
        "description": "investment_agent → sub_agent_invoked.",
        "event": make_json_event("investment_agent", {"domain": "investment", "draft_length": 200}),
        "expect_none": False,
        "expected_event_type": "sub_agent_invoked",
        "expected_component_name": "investment_agent",
        "expected_metadata_subset": {"domain": "investment"},
    },
    {
        "name": "sub_agent_pension",
        "description": "pension_agent → sub_agent_invoked.",
        "event": make_json_event("pension_agent", {"domain": "pension", "draft_length": 180}),
        "expect_none": False,
        "expected_event_type": "sub_agent_invoked",
        "expected_component_name": "pension_agent",
        "expected_metadata_subset": {"domain": "pension"},
    },
    # ── Response events ──────────────────────────────────────────────────────
    {
        "name": "response_written",
        "description": "response_writer_agent → response_written with response_length.",
        "event": make_json_event("response_writer_agent", {"response_length": 250}),
        "expect_none": False,
        "expected_event_type": "response_written",
        "expected_component_name": "response_writer_agent",
        "expected_metadata_subset": {"response_length": 250},
        "expected_output_summary": "response_length=250",
    },
    {
        "name": "final_response_plain_text",
        "description": "finance_verification_agent with plain text → final_response_delivered.",
        "event": make_text_event(
            "finance_verification_agent",
            "Here is your mortgage guidance. Please consult a qualified adviser.",
        ),
        "expect_none": False,
        "expected_event_type": "final_response_delivered",
        "expected_component_name": "finance_verification_agent",
        "expected_metadata_subset": {},
    },
    # ── Fallback / unknown authors ────────────────────────────────────────────
    {
        "name": "unknown_agent_suffix",
        "description": "Any *_agent suffix not in the explicit map falls back to sub_agent_invoked.",
        "event": make_json_event("custom_domain_agent", {"domain": "custom"}),
        "expect_none": False,
        "expected_event_type": "sub_agent_invoked",
        "expected_component_name": "custom_domain_agent",
        "expected_metadata_subset": {},
    },
    {
        "name": "unknown_author_no_suffix",
        "description": "Authors with no match and no _agent suffix → agent_event.",
        "event": make_text_event("some_middleware", "debug output"),
        "expect_none": False,
        "expected_event_type": "agent_event",
        "expected_component_name": "some_middleware",
        "expected_metadata_subset": {},
    },
    # ── Edge cases ────────────────────────────────────────────────────────────
    {
        "name": "empty_content",
        "description": "Event with no content still produces a TraceEvent (empty metadata).",
        "event": make_empty_event("safety_agent"),
        "expect_none": False,
        "expected_event_type": "safety_check_completed",
        "expected_component_name": "safety_agent",
        "expected_metadata_subset": {},
    },
    {
        "name": "float_timestamp",
        "description": "A float UNIX timestamp is converted to a tz-aware datetime.",
        "event": FakeAdkEvent(
            author="safety_agent",
            content=FakeAdkContent(parts=[FakePart(text='{"action": "allow"}')]),
            invocation_id="inv-float-ts",
            timestamp=_FIXED_UNIX_TS,
        ),
        "expect_none": False,
        "expected_event_type": "safety_check_completed",
        "expected_component_name": "safety_agent",
        "expected_metadata_subset": {"action": "allow"},
    },
]

# ---------------------------------------------------------------------------
# Convenience accessors
# ---------------------------------------------------------------------------


def get_scenario(name: str) -> dict[str, Any]:
    """Return a golden scenario by name."""
    for s in GOLDEN_EVENT_SCENARIOS:
        if s["name"] == name:
            return s
    raise KeyError(f"No golden scenario named {name!r}")


def nominal_turn_events(invocation_id: str = "inv-001") -> list[FakeAdkEvent]:
    """Return a complete six-event ADK sequence for a nominal mortgage turn."""
    return [
        make_json_event("safety_agent", {"action": "allow", "reason": "clean"}, invocation_id),
        make_json_event("intent_router_agent", {"domain": "mortgage", "confidence": 0.85}, invocation_id),
        make_json_event("route_selector", {"selected_domain": "mortgage"}, invocation_id),
        make_json_event("mortgage_agent", {"domain": "mortgage", "draft_length": 150}, invocation_id),
        make_json_event("response_writer_agent", {"response_length": 220}, invocation_id),
        make_text_event("finance_verification_agent", "Here is your mortgage guidance.", invocation_id),
    ]


def injection_turn_events(invocation_id: str = "inv-002") -> list[FakeAdkEvent]:
    """Return a four-event ADK sequence for a prompt-injection turn."""
    return [
        make_json_event(
            "safety_agent",
            {
                "action": "allow",
                "prompt_injection_detected": True,
                "safe_response_delivered": True,
                "instructions_leaked": False,
                "redirection_present": True,
            },
            invocation_id,
        ),
        make_json_event("intent_router_agent", {"domain": "investment", "confidence": 0.75}, invocation_id),
        make_json_event("route_selector", {"selected_domain": "investment"}, invocation_id),
        make_text_event("finance_verification_agent", "I cannot follow that request.", invocation_id),
    ]


def loop_risk_turn_events(invocation_id: str = "inv-003") -> list[FakeAdkEvent]:
    """Return ADK events that contain a repeated route_selected (loop risk trigger)."""
    return [
        make_json_event("safety_agent", {"action": "allow"}, invocation_id),
        make_json_event("intent_router_agent", {"domain": "investment", "confidence": 0.80}, invocation_id),
        make_json_event("route_selector", {"selected_domain": "investment"}, invocation_id),
        make_json_event("route_selector", {"selected_domain": "investment"}, invocation_id),  # repeated
        make_json_event("investment_agent", {"domain": "investment", "draft_length": 100}, invocation_id),
        make_json_event("investment_agent", {"domain": "investment", "draft_length": 100}, invocation_id),  # repeated
        make_json_event("response_writer_agent", {"response_length": 180}, invocation_id),
        make_text_event("finance_verification_agent", "Here is your investment information.", invocation_id),
    ]
