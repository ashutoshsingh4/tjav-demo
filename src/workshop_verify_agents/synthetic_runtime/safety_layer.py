"""Pre- and post-processing safety guardrails for agent responses.

Checks inbound queries for prompt-injection patterns and unsafe request
categories before any sub-agent processes them.  Returns a structured
``SafetyResult`` so the orchestrator can decide whether to proceed.

All checks are deterministic keyword/pattern-based rules — no external
calls required — making the module fast and locally runnable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from workshop_verify_agents.verification.trace_schema import ExecutionTrace, TraceEvent


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Phrases that indicate a prompt-injection attempt.
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\b.{0,30}\binstructions", re.I),
    re.compile(r"forget\b.{0,30}\binstructions", re.I),
    re.compile(r"you are now", re.I),
    re.compile(r"act as (a |an )?(?!financial)", re.I),  # "act as a DAN", etc.
    re.compile(r"jailbreak", re.I),
    re.compile(r"disregard (your |the )?(system |safety )?prompt", re.I),
    re.compile(r"<\s*(script|iframe|object|embed)", re.I),  # HTML injection
]

# Requests for definitive regulated advice that the agent cannot give.
_REGULATED_ADVICE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(guarantee|guarantees|guaranteed)\b.{0,40}\b(return|profit|gain)", re.I),
    re.compile(r"\bwill (definitely|certainly|always) (go up|increase|profit)", re.I),
    re.compile(r"\btell me exactly (what|which) (fund|stock|share|investment) to buy", re.I),
]

_FALLBACK_RESPONSE = (
    "I'm sorry, I'm not able to help with that request. "
    "Please ask me about mortgages, investments, or pensions."
)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class SafetyResult:
    """Outcome of a safety check."""

    safe: bool
    """True if the input passed all checks and processing may continue."""

    action: str
    """One of: ``'allow'``, ``'block'``, ``'warn'``."""

    reason: str | None = None
    """Human-readable reason when ``action`` is not ``'allow'``."""

    sanitised_input: str = ""
    """The (possibly unchanged) input text after any sanitisation."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check(
    user_input: str,
    conversation_id: str,
    turn_id: str,
    trace: ExecutionTrace,
) -> SafetyResult:
    """Run all safety checks on *user_input* and record events on *trace*.

    Emits a ``safety_check_started`` event, evaluates injection and regulated-
    advice patterns, then emits a ``safety_check_completed`` event with the
    outcome before returning a ``SafetyResult``.
    """
    trace.add_event(TraceEvent(
        conversation_id=conversation_id,
        turn_id=turn_id,
        component_name="safety_layer",
        event_type="safety_check_started",
        input_summary=user_input[:120],
        metadata={"input_length": len(user_input)},
    ))

    result = _evaluate(user_input)

    trace.add_event(TraceEvent(
        conversation_id=conversation_id,
        turn_id=turn_id,
        component_name="safety_layer",
        event_type="safety_check_completed",
        input_summary=user_input[:120],
        output_summary=result.reason or "all checks passed",
        metadata={
            "action": result.action,
            "safe": result.safe,
            "reason": result.reason,
        },
    ))

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _evaluate(text: str) -> SafetyResult:
    """Apply pattern checks and return a SafetyResult."""
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return SafetyResult(
                safe=False,
                action="block",
                reason=f"Prompt-injection pattern detected: '{pattern.pattern}'",
                sanitised_input=_FALLBACK_RESPONSE,
            )

    for pattern in _REGULATED_ADVICE_PATTERNS:
        if pattern.search(text):
            return SafetyResult(
                safe=False,
                action="block",
                reason="Request asks for regulated financial advice that cannot be provided.",
                sanitised_input=_FALLBACK_RESPONSE,
            )

    return SafetyResult(safe=True, action="allow", sanitised_input=text)
