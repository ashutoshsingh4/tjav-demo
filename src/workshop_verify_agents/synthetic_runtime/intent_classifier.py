"""Customer intent classifier for multi-turn financial conversations.

Uses a lightweight keyword-scoring approach: no LLM or external service
required.  Each domain accumulates a score based on how many of its keyword
terms appear in the query; the domain with the highest score wins.  A
confidence value of 0.0–1.0 is derived from the score margin.

Domains: ``mortgage``, ``investment``, ``pension``, ``general``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from workshop_verify_agents.verification.trace_schema import ExecutionTrace, TraceEvent


# ---------------------------------------------------------------------------
# Keyword vocabulary — deliberately generic, no proprietary product names
# ---------------------------------------------------------------------------

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "mortgage": [
        "mortgage", "remortgage", "homeloan", "home loan", "buy to let",
        "first.time buyer", "fixed rate", "variable rate", "loan to value",
        "ltv", "stamp duty", "repayment", "interest.only", "affordability",
        "deposit", "conveyancing", "surveyor",
    ],
    "investment": [
        "invest", "investment", "isa", "stocks", "shares", "equity", "fund",
        "portfolio", "etf", "dividend", "capital gain", "market", "risk",
        "return", "asset allocation", "rebalance", "bond", "gilt",
        "general investment account", "gia",
    ],
    "pension": [
        "pension", "retirement", "annuity", "drawdown", "sipp", "final salary",
        "defined benefit", "defined contribution", "state pension", "pot",
        "lump sum", "contribution", "national insurance", "ni record",
        "retire", "pension age",
    ],
}


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class IntentResult:
    """Outcome of intent classification for a single query."""

    domain: str
    """One of: ``'mortgage'``, ``'investment'``, ``'pension'``, ``'general'``."""

    confidence: float
    """Score in [0.0, 1.0]; higher means the classification is more certain."""

    scores: dict[str, int]
    """Raw keyword hit counts per domain, useful for debugging."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify(
    user_input: str,
    conversation_id: str,
    turn_id: str,
    trace: ExecutionTrace,
) -> IntentResult:
    """Classify *user_input* into a financial domain and record the event.

    Emits an ``intent_classified`` TraceEvent carrying the domain, confidence,
    and per-domain keyword scores.
    """
    result = _score(user_input)

    trace.add_event(TraceEvent(
        conversation_id=conversation_id,
        turn_id=turn_id,
        component_name="intent_classifier",
        event_type="intent_classified",
        input_summary=user_input[:120],
        output_summary=f"domain={result.domain} confidence={result.confidence:.2f}",
        metadata={
            "domain": result.domain,
            "confidence": result.confidence,
            "scores": result.scores,
        },
    ))

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _score(text: str) -> IntentResult:
    """Compute per-domain keyword hit counts and derive a winner + confidence."""
    normalised = text.lower()
    scores: dict[str, int] = {}

    for domain, keywords in _DOMAIN_KEYWORDS.items():
        hits = sum(
            1 for kw in keywords
            if re.search(r"\b" + kw + r"\b", normalised)
        )
        scores[domain] = hits

    best_domain = max(scores, key=lambda d: scores[d])
    best_score = scores[best_domain]

    if best_score == 0:
        return IntentResult(domain="general", confidence=0.0, scores=scores)

    total = sum(scores.values())
    confidence = round(best_score / total, 2) if total > 0 else 0.0

    return IntentResult(domain=best_domain, confidence=confidence, scores=scores)
