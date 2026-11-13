"""Unit tests for adk_trace_adapter.normalise_adk_events_to_execution_trace.

Covers every author→event_type mapping, metadata and output_summary extraction,
timestamp conversion, user-event skipping, edge cases, and a full six-event
sequence that validates the ordering guarantee.

All tests run without google-adk or any external service dependency.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from workshop_verify_agents.adk_runtime.adk_trace_adapter import (
    normalise_adk_events_to_execution_trace,
)
from tests.fixtures.adk_event_fixtures import (
    GOLDEN_EVENT_SCENARIOS,
    FakeAdkContent,
    FakeAdkEvent,
    FakePart,
    make_empty_event,
    make_json_event,
    make_text_event,
    nominal_turn_events,
    _FIXED_UNIX_TS,
)

_CONV = "unit-test-conv-001"

# ---------------------------------------------------------------------------
# Parametrised golden-scenario mapping tests
# ---------------------------------------------------------------------------

_non_skip_scenarios = [s for s in GOLDEN_EVENT_SCENARIOS if not s.get("expect_none")]
_skip_scenarios = [s for s in GOLDEN_EVENT_SCENARIOS if s.get("expect_none")]


@pytest.mark.parametrize("scenario", _non_skip_scenarios, ids=[s["name"] for s in _non_skip_scenarios])
def test_golden_event_type_mapping(scenario):
    """Each golden event produces a TraceEvent with the expected event_type."""
    trace = normalise_adk_events_to_execution_trace([scenario["event"]], _CONV)
    assert len(trace.events) == 1, f"Expected 1 event for {scenario['name']!r}"
    assert trace.events[0].event_type == scenario["expected_event_type"]


@pytest.mark.parametrize("scenario", _non_skip_scenarios, ids=[s["name"] for s in _non_skip_scenarios])
def test_golden_component_name_mapping(scenario):
    """component_name on each TraceEvent must equal the source author."""
    trace = normalise_adk_events_to_execution_trace([scenario["event"]], _CONV)
    assert trace.events[0].component_name == scenario["expected_component_name"]


@pytest.mark.parametrize("scenario", _non_skip_scenarios, ids=[s["name"] for s in _non_skip_scenarios])
def test_golden_metadata_subset(scenario):
    """Payload keys declared in expected_metadata_subset must appear in TraceEvent.metadata."""
    trace = normalise_adk_events_to_execution_trace([scenario["event"]], _CONV)
    event = trace.events[0]
    for key, expected in scenario.get("expected_metadata_subset", {}).items():
        assert key in event.metadata, f"metadata missing key {key!r} for scenario {scenario['name']!r}"
        assert event.metadata[key] == expected, (
            f"metadata[{key!r}]: expected {expected!r}, got {event.metadata[key]!r}"
        )


@pytest.mark.parametrize(
    "scenario",
    [s for s in _non_skip_scenarios if "expected_output_summary" in s],
    ids=[s["name"] for s in _non_skip_scenarios if "expected_output_summary" in s],
)
def test_golden_output_summary(scenario):
    """output_summary must equal the golden expectation where one is specified."""
    trace = normalise_adk_events_to_execution_trace([scenario["event"]], _CONV)
    assert trace.events[0].output_summary == scenario["expected_output_summary"]


@pytest.mark.parametrize("scenario", _skip_scenarios, ids=[s["name"] for s in _skip_scenarios])
def test_golden_skipped_events(scenario):
    """Events in the skip list must not appear in the resulting trace."""
    trace = normalise_adk_events_to_execution_trace([scenario["event"]], _CONV)
    assert trace.events == [], f"Expected no events for {scenario['name']!r}"


# ---------------------------------------------------------------------------
# User / skip-filter tests
# ---------------------------------------------------------------------------


def test_empty_author_coerced_to_unknown_not_skipped():
    """An empty author string becomes 'unknown' via _safe_str; the event is kept."""
    event = FakeAdkEvent(author="", content=None)
    trace = normalise_adk_events_to_execution_trace([event], _CONV)
    assert len(trace.events) == 1
    assert trace.events[0].component_name == "unknown"
    assert trace.events[0].event_type == "agent_event"


def test_user_event_alone_produces_empty_trace():
    trace = normalise_adk_events_to_execution_trace([make_text_event("user", "Hello")], _CONV)
    assert trace.events == []


def test_user_event_mixed_with_agent_event_filtered():
    events = [
        make_text_event("user", "query"),
        make_json_event("safety_agent", {"action": "allow"}),
    ]
    trace = normalise_adk_events_to_execution_trace(events, _CONV)
    assert len(trace.events) == 1
    assert trace.events[0].event_type == "safety_check_completed"


def test_empty_event_list_returns_empty_trace():
    trace = normalise_adk_events_to_execution_trace([], _CONV)
    assert trace.conversation_id == _CONV
    assert trace.events == []


def test_only_user_events_returns_empty_trace():
    events = [make_text_event("user", "hi"), make_text_event("user", "bye")]
    trace = normalise_adk_events_to_execution_trace(events, _CONV)
    assert trace.events == []


# ---------------------------------------------------------------------------
# conversation_id and turn_id propagation
# ---------------------------------------------------------------------------


def test_conversation_id_on_trace():
    trace = normalise_adk_events_to_execution_trace(
        [make_json_event("safety_agent", {"action": "allow"})], "my-conv-xyz"
    )
    assert trace.conversation_id == "my-conv-xyz"


def test_conversation_id_propagated_to_all_events():
    events = [
        make_json_event("safety_agent", {"action": "allow"}, "inv-t"),
        make_json_event("intent_router_agent", {"domain": "mortgage", "confidence": 0.8}, "inv-t"),
    ]
    trace = normalise_adk_events_to_execution_trace(events, "prop-conv")
    assert all(e.conversation_id == "prop-conv" for e in trace.events)


def test_invocation_id_becomes_turn_id():
    event = make_json_event("safety_agent", {"action": "allow"}, invocation_id="turn-abc")
    trace = normalise_adk_events_to_execution_trace([event], _CONV)
    assert trace.events[0].turn_id == "turn-abc"


def test_missing_invocation_id_falls_back_to_conversation_id():
    event = FakeAdkEvent(
        author="safety_agent",
        content=FakeAdkContent(parts=[FakePart(text='{"action":"allow"}')]),
        invocation_id=None,
    )
    trace = normalise_adk_events_to_execution_trace([event], _CONV)
    assert trace.events[0].turn_id == _CONV


# ---------------------------------------------------------------------------
# Timestamp extraction
# ---------------------------------------------------------------------------


def test_datetime_timestamp_preserved():
    ts = datetime(2026, 3, 15, 9, 30, 0, tzinfo=timezone.utc)
    event = FakeAdkEvent(
        author="safety_agent",
        content=FakeAdkContent(parts=[FakePart(text='{"action":"allow"}')]),
        timestamp=ts,
    )
    trace = normalise_adk_events_to_execution_trace([event], _CONV)
    assert trace.events[0].timestamp == ts


def test_float_unix_timestamp_converted_to_utc_datetime():
    event = FakeAdkEvent(
        author="intent_router_agent",
        content=FakeAdkContent(parts=[FakePart(text='{"domain":"mortgage","confidence":0.9}')]),
        invocation_id="inv-ts",
        timestamp=_FIXED_UNIX_TS,
    )
    trace = normalise_adk_events_to_execution_trace([event], _CONV)
    expected = datetime.fromtimestamp(_FIXED_UNIX_TS, tz=timezone.utc)
    assert trace.events[0].timestamp == expected


def test_none_timestamp_falls_back_to_utc_now_and_does_not_raise():
    event = FakeAdkEvent(
        author="safety_agent",
        content=FakeAdkContent(parts=[FakePart(text='{"action":"allow"}')]),
        timestamp=None,
    )
    trace = normalise_adk_events_to_execution_trace([event], _CONV)
    assert trace.events[0].timestamp is not None
    assert trace.events[0].timestamp.tzinfo is not None


def test_naive_datetime_gets_utc_tzinfo():
    naive_ts = datetime(2026, 1, 1, 0, 0, 0)
    event = FakeAdkEvent(
        author="safety_agent",
        content=FakeAdkContent(parts=[FakePart(text='{"action":"allow"}')]),
        timestamp=naive_ts,
    )
    trace = normalise_adk_events_to_execution_trace([event], _CONV)
    assert trace.events[0].timestamp.tzinfo is not None


# ---------------------------------------------------------------------------
# Output summary derivation
# ---------------------------------------------------------------------------


def test_safety_allow_output_summary_without_reason():
    trace = normalise_adk_events_to_execution_trace(
        [make_json_event("safety_agent", {"action": "allow"})], _CONV
    )
    assert trace.events[0].output_summary == "action=allow"


def test_safety_allow_output_summary_with_reason():
    trace = normalise_adk_events_to_execution_trace(
        [make_json_event("safety_agent", {"action": "allow", "reason": "clean"})], _CONV
    )
    assert trace.events[0].output_summary == "action=allow — clean"


def test_intent_classified_output_summary_format():
    trace = normalise_adk_events_to_execution_trace(
        [make_json_event("intent_router_agent", {"domain": "pension", "confidence": 0.92})], _CONV
    )
    assert trace.events[0].output_summary == "domain=pension confidence=0.92"


def test_route_selected_output_summary():
    trace = normalise_adk_events_to_execution_trace(
        [make_json_event("route_selector", {"selected_domain": "mortgage"})], _CONV
    )
    assert trace.events[0].output_summary == "domain=mortgage"


def test_response_written_output_summary():
    trace = normalise_adk_events_to_execution_trace(
        [make_json_event("response_writer_agent", {"response_length": 312})], _CONV
    )
    assert trace.events[0].output_summary == "response_length=312"


def test_final_response_output_summary_capped_at_120_chars():
    long_text = "A" * 200
    trace = normalise_adk_events_to_execution_trace(
        [make_text_event("finance_verification_agent", long_text)], _CONV
    )
    assert len(trace.events[0].output_summary) <= 120


# ---------------------------------------------------------------------------
# Full six-event nominal sequence
# ---------------------------------------------------------------------------


def test_nominal_sequence_event_count():
    trace = normalise_adk_events_to_execution_trace(nominal_turn_events(), _CONV)
    assert len(trace.events) == 6


def test_nominal_sequence_event_type_order():
    trace = normalise_adk_events_to_execution_trace(nominal_turn_events(), _CONV)
    assert [e.event_type for e in trace.events] == [
        "safety_check_completed",
        "intent_classified",
        "route_selected",
        "sub_agent_invoked",
        "response_written",
        "final_response_delivered",
    ]


def test_nominal_sequence_all_events_share_conversation_id():
    trace = normalise_adk_events_to_execution_trace(nominal_turn_events("inv-seq"), "seq-conv")
    assert all(e.conversation_id == "seq-conv" for e in trace.events)


def test_nominal_sequence_all_events_share_turn_id():
    trace = normalise_adk_events_to_execution_trace(nominal_turn_events("inv-shared"), _CONV)
    assert all(e.turn_id == "inv-shared" for e in trace.events)


def test_nominal_sequence_non_json_content_does_not_raise():
    events = list(nominal_turn_events())
    events.append(make_text_event("some_logger", "INFO: pipeline complete"))
    trace = normalise_adk_events_to_execution_trace(events, _CONV)
    assert len(trace.events) == 7
