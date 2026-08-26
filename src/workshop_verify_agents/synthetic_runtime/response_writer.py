"""Final response formatter for customer-facing messages.

Rewrites a raw sub-agent draft into a consistent, guidance-oriented tone:
- First-person plural voice ("We recommend …")
- Appends a standard regulatory disclaimer
- Adds a domain-appropriate prompt to seek professional advice when relevant

No external calls required; all transformations are deterministic string
operations suitable for a research prototype.
"""

from __future__ import annotations

from workshop_verify_agents.verification.trace_schema import ExecutionTrace, TraceEvent


# ---------------------------------------------------------------------------
# Disclaimer library
# ---------------------------------------------------------------------------

_GENERAL_DISCLAIMER = (
    "This information is for general educational purposes only and does not "
    "constitute regulated financial advice.  Your individual circumstances may "
    "differ; please consider seeking independent financial advice before making "
    "any financial decisions."
)

_DOMAIN_PROMPTS: dict[str, str] = {
    "mortgage": (
        "If you would like to discuss your specific mortgage situation, a qualified "
        "mortgage adviser can provide personalised guidance."
    ),
    "investment": (
        "For personalised investment recommendations based on your risk profile and "
        "objectives, please consult a regulated investment adviser."
    ),
    "pension": (
        "Pension planning is highly individual; a regulated financial planner can "
        "help you build a retirement strategy tailored to your needs."
    ),
    "general": "",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def write(
    draft: str,
    domain: str,
    conversation_id: str,
    turn_id: str,
    trace: ExecutionTrace,
) -> str:
    """Rewrite *draft* into a consistent guidance tone and emit a trace event.

    Applies light formatting, appends the standard disclaimer, and adds a
    domain-specific call-to-action.  Returns the final customer-facing response.
    """
    response = _format(draft, domain)

    trace.add_event(TraceEvent(
        conversation_id=conversation_id,
        turn_id=turn_id,
        component_name="response_writer",
        event_type="response_written",
        input_summary=draft[:120],
        output_summary=response[:120],
        metadata={"domain": domain, "response_length": len(response)},
    ))

    return response


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _format(draft: str, domain: str) -> str:
    """Assemble the final response from a draft, disclaimer, and domain prompt."""
    parts: list[str] = [draft.strip()]

    domain_prompt = _DOMAIN_PROMPTS.get(domain, "")
    if domain_prompt:
        parts.append(domain_prompt)

    parts.append(_GENERAL_DISCLAIMER)

    return "\n\n".join(parts)
