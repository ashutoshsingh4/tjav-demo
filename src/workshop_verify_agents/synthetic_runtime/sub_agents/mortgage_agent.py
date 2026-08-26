"""Domain sub-agent for mortgage-related customer queries.

Produces deterministic draft answers from a small lookup table of synthetic
mortgage guidance topics.  No external calls or LLM required.

The lookup is intentionally simplified and generic — suitable for a research
prototype and external publication.  Real products, lenders, and rates are
not referenced.
"""

from __future__ import annotations

from workshop_verify_agents.verification.trace_schema import ExecutionTrace, TraceEvent


# ---------------------------------------------------------------------------
# Synthetic guidance library
# ---------------------------------------------------------------------------

_GUIDANCE: dict[str, str] = {
    "affordability": (
        "Mortgage affordability is typically assessed based on your annual income "
        "and existing financial commitments.  Most lenders use an income multiple "
        "(commonly 4–4.5×) as an initial estimate.  A formal affordability check "
        "will also consider your monthly outgoings and credit history."
    ),
    "deposit": (
        "A deposit of at least 5% of the property value is generally required for "
        "a residential mortgage.  A larger deposit (10–20%+) usually unlocks better "
        "interest rates and a wider choice of products."
    ),
    "fixed_rate": (
        "A fixed-rate mortgage keeps your monthly repayment unchanged for an agreed "
        "initial period (commonly 2, 3, or 5 years).  After that period, you "
        "typically move to the lender's standard variable rate unless you remortgage."
    ),
    "interest_only": (
        "With an interest-only mortgage you pay only the interest each month; the "
        "capital balance stays the same.  You must have a credible repayment vehicle "
        "(e.g. investments, savings, property sale) in place to repay the capital "
        "at the end of the term."
    ),
    "remortgage": (
        "Remortgaging means switching your existing mortgage to a new deal, either "
        "with your current lender or a new one.  Common reasons include securing a "
        "lower rate, releasing equity, or changing the mortgage term."
    ),
    "default": (
        "Mortgages are long-term loans secured against residential property.  "
        "Key factors to understand include the loan-to-value ratio, the interest "
        "rate type (fixed or variable), the repayment method, and the total cost "
        "over the mortgage term.  Always consider seeking independent financial "
        "advice before committing to a mortgage product."
    ),
}

_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "affordability": ["afford", "income", "salary", "earn", "borrow", "how much"],
    "deposit": ["deposit", "down payment", "upfront", "5%", "10%", "20%"],
    "fixed_rate": ["fixed", "fixed-rate", "fixed rate", "fixed term"],
    "interest_only": ["interest only", "interest-only", "repayment vehicle"],
    "remortgage": ["remortgage", "re-mortgage", "switch", "new deal"],
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def handle(
    user_input: str,
    conversation_id: str,
    turn_id: str,
    trace: ExecutionTrace,
) -> str:
    """Produce a draft mortgage guidance response and emit a trace event."""
    topic = _detect_topic(user_input)
    draft = _GUIDANCE.get(topic, _GUIDANCE["default"])

    trace.add_event(TraceEvent(
        conversation_id=conversation_id,
        turn_id=turn_id,
        component_name="mortgage_agent",
        event_type="sub_agent_invoked",
        input_summary=user_input[:120],
        output_summary=f"topic={topic}",
        metadata={"domain": "mortgage", "topic": topic},
    ))

    return draft


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _detect_topic(text: str) -> str:
    """Return the best-matching guidance topic key for *text*."""
    lower = text.lower()
    for topic, keywords in _TOPIC_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return topic
    return "default"
