"""Domain sub-agent for investment-related customer queries.

Produces deterministic draft answers from a small lookup table of synthetic
investment guidance topics.  No external calls or LLM required.

All guidance is generic and educational — no specific funds, products, or
expected returns are cited.
"""

from __future__ import annotations

from workshop_verify_agents.verification.trace_schema import ExecutionTrace, TraceEvent


# ---------------------------------------------------------------------------
# Synthetic guidance library
# ---------------------------------------------------------------------------

_GUIDANCE: dict[str, str] = {
    "risk": (
        "Investment risk refers to the possibility that the value of your investment "
        "will fall as well as rise.  Generally, investments with higher potential "
        "returns carry higher risk.  Your risk tolerance depends on factors such as "
        "your investment horizon, financial circumstances, and personal comfort with "
        "volatility.  A suitability assessment can help identify an appropriate "
        "risk level for your situation."
    ),
    "isa": (
        "An Individual Savings Account (ISA) allows you to invest or save up to a "
        "set annual allowance without paying tax on returns or withdrawals.  Common "
        "types include the Cash ISA, Stocks and Shares ISA, and Innovative Finance "
        "ISA.  Contributions cannot exceed the annual subscription limit set by the "
        "relevant tax authority."
    ),
    "diversification": (
        "Diversification involves spreading investments across different asset "
        "classes, geographies, and sectors to reduce the impact of any single "
        "investment performing poorly.  A diversified portfolio does not eliminate "
        "risk but can reduce unsystematic (company-specific) risk."
    ),
    "bonds": (
        "Bonds are debt instruments issued by governments or corporations.  They "
        "typically pay a fixed interest rate (coupon) and return the principal at "
        "maturity.  Bonds are generally considered lower risk than equities but "
        "are subject to interest-rate risk and credit risk."
    ),
    "funds": (
        "Investment funds pool money from multiple investors to buy a diversified "
        "portfolio of assets.  Types include unit trusts, OEICs, and exchange-traded "
        "funds (ETFs).  Funds charge ongoing fees (OCF/TER) which affect net returns."
    ),
    "default": (
        "Investing involves putting money to work with the goal of achieving a "
        "return over time.  Key principles include understanding your investment "
        "objective, time horizon, and risk tolerance before selecting any product.  "
        "Independent financial advice is recommended before making investment "
        "decisions."
    ),
}

_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "risk": ["risk", "volatile", "volatility", "lose", "loss", "safe"],
    "isa": ["isa", "individual savings", "tax-free", "tax free"],
    "diversification": ["diversif", "spread", "asset allocation", "rebalance"],
    "bonds": ["bond", "gilt", "fixed income", "coupon", "maturity"],
    "funds": ["fund", "etf", "unit trust", "oeic", "tracker"],
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
    """Produce a draft investment guidance response and emit a trace event."""
    topic = _detect_topic(user_input)
    draft = _GUIDANCE.get(topic, _GUIDANCE["default"])

    trace.add_event(TraceEvent(
        conversation_id=conversation_id,
        turn_id=turn_id,
        component_name="investment_agent",
        event_type="sub_agent_invoked",
        input_summary=user_input[:120],
        output_summary=f"topic={topic}",
        metadata={"domain": "investment", "topic": topic},
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
