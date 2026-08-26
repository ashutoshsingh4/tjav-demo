"""Demo entry point for the workshop verification module.

Run with:
    uv run python -m workshop_verify_agents.app
    uv run python -m workshop_verify_agents.app --mode synthetic --query "..."
    uv run python -m workshop_verify_agents.app --mode adk      --query "..."

Modes
-----
synthetic (default)
    Uses the deterministic rule-based agent pipeline in
    ``workshop_verify_agents.synthetic_runtime``.  No LLM credentials required.

adk
    Uses the real Google ADK agent pipeline in
    ``workshop_verify_agents.adk_runtime``.  Requires ``OPENAI_API_KEY``
    in ``.env``.

Both modes feed the same generic verification pipeline:
    ExecutionTrace → BusinessSignals → BehaviourEvidence → BehaviourAssessment
"""

from __future__ import annotations

import argparse
import textwrap
from uuid import uuid4

from workshop_verify_agents.synthetic_runtime.orchestrator import run as _synthetic_run
from workshop_verify_agents.verification.evidence_schema import (
    AssessmentStatus,
    EvidenceStatus,
    VerificationAssessment,
    VerificationEvidence,
)
from workshop_verify_agents.verification.online_verifier import verify_turn_behaviour
from workshop_verify_agents.verification.signal_schema import BusinessSignal
from workshop_verify_agents.verification.trace_schema import ExecutionTrace

# ANSI colour helpers
_BOLD   = "\033[1m"
_CYAN   = "\033[96m"
_GREEN  = "\033[92m"
_YELLOW = "\033[93m"
_RED    = "\033[91m"
_RESET  = "\033[0m"

_SEVERITY_COLOUR = {
    "low":      _GREEN,
    "medium":   _YELLOW,
    "high":     _RED,
    "critical": _BOLD + _RED,
}
_STATUS_COLOUR = {
    EvidenceStatus.pass_:         _GREEN,
    EvidenceStatus.warning:       _YELLOW,
    EvidenceStatus.fail:          _BOLD + _RED,
    EvidenceStatus.indeterminate: _CYAN,
}
_ASSESSMENT_COLOUR = {
    AssessmentStatus.pass_:               _GREEN,
    AssessmentStatus.pass_with_warnings:  _YELLOW,
    AssessmentStatus.fail:                _BOLD + _RED,
    AssessmentStatus.indeterminate:       _CYAN,
}

_DEFAULT_QUERY = (
    "I'm a first-time buyer — how does mortgage affordability work "
    "and how much can I typically borrow?"
)


# ---------------------------------------------------------------------------
# Mode-specific pipeline entry points
# ---------------------------------------------------------------------------

def _run_synthetic(query: str) -> tuple[str, ExecutionTrace]:
    """Run one turn through the deterministic synthetic agent pipeline."""
    result = _synthetic_run(query)
    return result.final_response, result.execution_trace


def _run_adk(query: str, conversation_id: str) -> tuple[str, ExecutionTrace]:
    """Run one turn through the real ADK agent pipeline.

    Imports are deferred so that a missing ``.env`` does not break
    ``--mode synthetic``.
    """
    try:
        from workshop_verify_agents.adk_runtime.runner import run_adk_conversation
    except OSError as exc:
        print(f"\n{_BOLD + _RED}ADK mode unavailable:{_RESET} {exc}")
        print("Set OPENAI_API_KEY in your .env file.")
        raise SystemExit(1) from exc

    return run_adk_conversation(query, conversation_id)


# ---------------------------------------------------------------------------
# Public demo runner
# ---------------------------------------------------------------------------

def demo(query: str = _DEFAULT_QUERY, mode: str = "synthetic") -> None:
    """Run one conversation turn through online behaviour verification.

    Parameters
    ----------
    query:
        The customer query to process.
    mode:
        ``'synthetic'`` (default) or ``'adk'``.
    """
    conversation_id = str(uuid4())
    mode_label = mode.upper()

    _print_header(f"INPUT QUERY  [{mode_label} MODE]")
    print(textwrap.fill(query, width=80))
    print()

    # ── Mode-specific agent pipeline ────────────────────────────────────────
    if mode == "adk":
        final_response, execution_trace = _run_adk(query, conversation_id)
    else:
        final_response, execution_trace = _run_synthetic(query)

    _print_header("FINAL RESPONSE")
    print(textwrap.fill(final_response, width=80))
    print()

    # ── Section 1: Raw trace events ─────────────────────────────────────────
    _print_header("1 - RAW TRACE EVENTS")
    for i, event in enumerate(execution_trace.events, start=1):
        ts = event.timestamp.strftime("%H:%M:%S.%f")[:-3]
        print(
            f"  {i:>2}. [{ts}]  {_CYAN}{event.event_type:<30}{_RESET}"
            f"  component={event.component_name}"
        )
        if event.output_summary:
            print(f"        -> {event.output_summary}")
    print()

    turn_result = verify_turn_behaviour(
        conversation_id=execution_trace.conversation_id,
        turn_index=0,
        execution_trace=execution_trace,
    )

    # ── Section 2: Business signals ─────────────────────────────────────────
    signals = turn_result.business_signals
    _print_header("2 - EXTRACTED BUSINESS SIGNALS")
    _print_signals_table(signals)
    print()

    # ── Section 3: Verification evidence ────────────────────────────────────
    evidence_items = turn_result.behaviour_evidence
    _print_header("3 - VERIFICATION EVIDENCE")
    _print_evidence_table(evidence_items)
    print()

    # ── Section 4: Verification assessment ──────────────────────────────────
    assessment = turn_result.behaviour_assessment or VerificationAssessment(
        conversation_id=execution_trace.conversation_id,
        overall_status=AssessmentStatus.indeterminate,
        summary="Online behaviour verification did not produce an assessment.",
    )
    _print_header("4 - VERIFICATION ASSESSMENT")
    _print_assessment(assessment)
    print()


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _print_header(title: str) -> None:
    bar = "-" * 72
    print(f"\n{_BOLD}{bar}{_RESET}")
    print(f"{_BOLD}  {title}{_RESET}")
    print(f"{_BOLD}{bar}{_RESET}")


def _print_signals_table(signals: list[BusinessSignal]) -> None:
    if not signals:
        print("  (no signals)")
        return
    header = f"  {'#':>3}  {'signal_name':<34}  {'type':<12}  {'sev':<10}  {'conf':>5}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for i, sig in enumerate(signals, start=1):
        colour = _SEVERITY_COLOUR.get(sig.severity.value, "")
        print(
            f"  {i:>3}. {sig.signal_name:<34}  {sig.signal_type.value:<12}"
            f"  {colour}{sig.severity.value:<10}{_RESET}  {sig.confidence:>4.0%}"
        )
        if sig.explanation:
            for line in textwrap.wrap(sig.explanation, width=66):
                print(f"        {line}")


def _print_evidence_table(items: list[VerificationEvidence]) -> None:
    if not items:
        print("  (no evidence)")
        return
    for ev in items:
        colour = _STATUS_COLOUR.get(ev.status, "")
        status_str = ev.status.value.upper()
        print(
            f"  {_BOLD}{ev.evidence_type.value.upper():<14}{_RESET}"
            f"  {colour}{status_str:<22}{_RESET}"
            f"  ({len(ev.related_signals)} signal(s))"
        )
        if ev.explanation:
            for line in textwrap.wrap(ev.explanation, width=68):
                print(f"    {line}")
        print()


def _print_assessment(assessment: VerificationAssessment) -> None:
    colour = _ASSESSMENT_COLOUR.get(assessment.overall_status, "")
    print(
        f"  Overall status:  "
        f"{colour}{_BOLD}{assessment.overall_status.value.upper()}{_RESET}"
    )
    print()

    if assessment.summary:
        for line in textwrap.wrap(assessment.summary, width=72):
            print(f"  {line}")
        print()

    if assessment.failures:
        print(f"  {_BOLD + _RED}Failures:{_RESET}")
        for f in assessment.failures:
            for line in textwrap.wrap(f"- {f}", width=70):
                print(f"    {line}")
        print()

    if assessment.warnings:
        print(f"  {_BOLD + _YELLOW}Warnings:{_RESET}")
        for w in assessment.warnings:
            for line in textwrap.wrap(f"- {w}", width=70):
                print(f"    {line}")
        print()

    if not assessment.failures and not assessment.warnings:
        print(f"  {_GREEN}No failures or warnings.{_RESET}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Workshop verification demo — run one conversation turn end-to-end."
    )
    parser.add_argument(
        "--query",
        default=_DEFAULT_QUERY,
        help="Customer query to process.",
    )
    parser.add_argument(
        "--mode",
        choices=["synthetic", "adk"],
        default="synthetic",
        help=(
            "Agent runtime mode. "
            "'synthetic' uses deterministic rule-based agents (default, no credentials needed). "
            "'adk' uses the real Google ADK pipeline (requires .env credentials)."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    demo(args.query, mode=args.mode)



