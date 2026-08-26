"""Intent router agent for the ADK runtime demo.

Classifies a customer query into one of four domains: mortgage, investment,
pension, or general.  Defined as an ADK Agent for dev-UI visibility; the root
orchestrator calls its instruction via a direct LLM call and parses the
structured JSON response.
"""

from __future__ import annotations

from google.adk import Agent

from .model_provider import get_llm

intent_router_agent = Agent(
    name="intent_router_agent",
    model=get_llm(),
    description="Classifies a customer query into a financial domain.",
    instruction=(
        "You are an intent classifier for a financial guidance assistant.\n"
        "\n"
        "Classify the user's query into exactly one of these domains:\n"
        "  - mortgage   : questions about home loans, remortgaging, affordability\n"
        "  - investment : questions about ISAs, funds, stocks, risk, portfolio\n"
        "  - pension    : questions about retirement, drawdown, annuities, contributions\n"
        "  - general    : any other financial or non-financial topic\n"
        "\n"
        "Respond with JSON only:\n"
        '{"domain": "mortgage"|"investment"|"pension"|"general", '
        '"confidence": 0.0-1.0, "reasoning": "<one sentence>"}\n'
        "\n"
        "Do not include any text outside the JSON object."
    ),
)
