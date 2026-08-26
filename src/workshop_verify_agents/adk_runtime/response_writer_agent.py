"""Response writer agent for the ADK runtime demo.

Rewrites a domain sub-agent's draft response into a consistent, guidance-oriented
tone with appropriate regulatory disclaimers.  Defined as an ADK Agent for
observability; invoked via direct LLM call from the root orchestrator.
"""

from __future__ import annotations

from google.adk import Agent

from .model_provider import get_llm

response_writer_agent = Agent(
    name="response_writer_agent",
    model=get_llm(),
    description="Rewrites domain draft responses into a consistent customer-facing tone.",
    instruction=(
        "You are a response writer for a financial guidance assistant.\n"
        "\n"
        "You will receive a draft response from a domain specialist. "
        "Your job is to rewrite it into a clear, warm, and appropriately cautious "
        "customer-facing message.\n"
        "\n"
        "Guidelines:\n"
        "- Use plain, accessible English — avoid jargon where possible\n"
        "- Keep the response focused and concise\n"
        "- Preserve all the factual content of the draft\n"
        "- End with a brief disclaimer that this is general educational "
        "  information only and does not constitute regulated financial advice\n"
        "- If the draft mentions a topic requiring professional advice (pension "
        "  transfers, investment suitability), reinforce that recommendation\n"
        "\n"
        "Do not add new claims, product recommendations, or guaranteed outcomes. "
        "Do not remove safety-relevant caveats from the draft."
    ),
)
