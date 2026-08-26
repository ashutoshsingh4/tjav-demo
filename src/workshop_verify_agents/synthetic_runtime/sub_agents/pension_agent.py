"""Domain sub-agent for pension-related customer queries.

Produces deterministic draft answers from a small lookup table of synthetic
pension guidance topics.  No external calls or LLM required.

All guidance is generic and educational.  Regulated pension transfer or
drawdown advice is flagged as out-of-scope and redirected to an adviser.
"""

from __future__ import annotations

from workshop_verify_agents.verification.trace_schema import ExecutionTrace, TraceEvent


# ---------------------------------------------------------------------------
# Synthetic guidance library
# ---------------------------------------------------------------------------

_GUIDANCE: dict[str, str] = {
    "state_pension": (
        "The state pension is a regular payment from the government available once "
        "you reach state pension age.  The amount you receive depends on your "
        "National Insurance record.  You typically need a minimum number of "
        "qualifying years to receive any state pension, and a higher number for the "
        "full amount.  You can obtain a state pension forecast from the government's "
        "online service."
    ),
    "workplace_pension": (
        "A workplace pension is a pension scheme arranged by your employer.  Both "
        "you and your employer usually make contributions, and you may also benefit "
        "from tax relief on your contributions.  Auto-enrolment rules require most "
        "employers to enrol eligible workers automatically."
    ),
    "drawdown": (
        "Pension drawdown allows you to keep your pension pot invested while drawing "
        "an income from it.  Unlike an annuity, the income is not guaranteed and "
        "depends on investment performance.  Drawdown decisions are complex and "
        "regulated; we strongly recommend seeking independent financial advice before "
        "proceeding."
    ),
    "annuity": (
        "An annuity converts your pension pot into a guaranteed income for life (or "
        "a fixed term).  The rate you receive depends on factors such as your age, "
        "health, and the annuity type.  Once purchased, most annuities cannot be "
        "changed, so it is important to shop around and consider your options "
        "carefully."
    ),
    "contribution": (
        "Increasing your pension contributions — even by a small amount — can "
        "significantly improve your retirement income thanks to the effect of "
        "compound growth over time.  Contributions benefit from tax relief at your "
        "marginal rate, up to the annual allowance set by tax rules."
    ),
    "transfer": (
        "Transferring a pension is a regulated activity.  If you are considering "
        "consolidating pension pots or transferring a defined-benefit (final salary) "
        "scheme, you must receive regulated financial advice.  This guidance cannot "
        "advise you on whether a transfer is suitable for you."
    ),
    "default": (
        "Pensions are long-term savings vehicles designed to provide income in "
        "retirement.  The main types are workplace pensions, personal pensions, and "
        "the state pension.  Tax relief on contributions and tax-free growth make "
        "pensions one of the most tax-efficient ways to save for retirement.  For "
        "personalised retirement planning, please consult a regulated financial "
        "adviser."
    ),
}

_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "state_pension": ["state pension", "national insurance", "ni record", "government pension"],
    "workplace_pension": ["workplace", "employer", "auto-enrol", "auto enrol", "company pension"],
    "drawdown": ["drawdown", "draw down", "flexible access", "income drawdown"],
    "annuity": ["annuity", "annuities", "guaranteed income", "lifetime income"],
    "contribution": ["contribut", "pay in", "top up", "increase", "how much should i"],
    "transfer": ["transfer", "consolidat", "move my pension", "combine"],
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
    """Produce a draft pension guidance response and emit a trace event."""
    topic = _detect_topic(user_input)
    draft = _GUIDANCE.get(topic, _GUIDANCE["default"])

    trace.add_event(TraceEvent(
        conversation_id=conversation_id,
        turn_id=turn_id,
        component_name="pension_agent",
        event_type="sub_agent_invoked",
        input_summary=user_input[:120],
        output_summary=f"topic={topic}",
        metadata={"domain": "pension", "topic": topic},
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
