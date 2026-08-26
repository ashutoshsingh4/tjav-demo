"""Root orchestrator agent for the ADK runtime verification demo.

This module implements a custom ``BaseAgent`` workflow orchestrator named
``FinanceVerificationAgent``. It is intentionally not a native ADK sub-agent
delegation tree.

Design intent
-------------
- The orchestrator manually controls the workflow steps for trace-derived
  verification: safety check, intent classification, route selection, domain
  response generation, response rewriting, and final response delivery.
- The domain ADK Agent objects imported below are used as modular instruction
  definitions. Their ``.instruction`` strings are passed into direct LLM calls
  to keep the runtime deterministic and the trace semantics explicit.
- The orchestrator emits semantic ``Event`` objects so that
  ``adk_trace_adapter`` can normalize them into ``ExecutionTrace`` / business
  signals for verification.
- This is a deliberate workshop design choice, not a claim of native ADK
  sub-agent delegation.

Pipeline per turn
-----------------
1. Safety check (pattern rules + optional LLM fallback)
    → safety_check_started, safety_check_completed
2. Intent classification (LLM structured output)
    → intent_classified
3. Route selection
    → route_selected
4. Domain agent LLM call (uses the domain agent instruction as a prompt)
    → sub_agent_invoked
5. Response writer LLM call
    → response_written
6. Final response delivery event (plain text, delivered to the caller)
    → final_response_delivered

The workflow is intentionally explicit so its event semantics are easy to
inspect in the accompanying verification pipeline.
"""

from __future__ import annotations

import json
import re
from typing import AsyncGenerator

from pydantic import ValidationError
from typing_extensions import override

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.models.llm_request import LlmRequest
from google.genai import types

from .model_provider import get_llm
from .safety_agent import safety_agent
from .intent_router_agent import intent_router_agent
from .mortgage_agent import mortgage_agent
from .investment_agent import investment_agent
from .pension_agent import pension_agent
from .response_writer_agent import response_writer_agent

_llm = get_llm()

# ---------------------------------------------------------------------------
# Semantic event names (kept stable for the trace adapter)
# ---------------------------------------------------------------------------

EVENT_AUTHOR_SAFETY_CHECK_STARTED = "safety_check_started"
EVENT_AUTHOR_SAFETY_AGENT = "safety_agent"
EVENT_AUTHOR_INTENT_ROUTER_AGENT = "intent_router_agent"
EVENT_AUTHOR_ROUTE_SELECTOR = "route_selector"
EVENT_AUTHOR_RESPONSE_WRITER_AGENT = "response_writer_agent"
EVENT_AUTHOR_FINAL_RESPONSE = "finance_verification_agent"

EVENT_TYPE_FINAL_RESPONSE_DELIVERED = "final_response_delivered"

# ---------------------------------------------------------------------------
# Prompt-injection patterns (deterministic; no LLM call required)
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\b.{0,30}\binstructions", re.I),
    re.compile(r"forget\b.{0,30}\binstructions", re.I),
    re.compile(r"you are now\b", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"disregard (your |the )?(system |safety )?prompt", re.I),
    re.compile(r"<\s*(script|iframe|object|embed)", re.I),
]

_GUARANTEED_RETURN_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(guarantee|guarantees|guaranteed)\b.{0,40}\b(return|profit|gain)", re.I),
    re.compile(r"\bwill (definitely|certainly|always) (go up|increase|profit)", re.I),
]

_FALLBACK_RESPONSE = (
    "I'm sorry, I'm not able to help with that request. "
    "Please ask me about mortgages, investments, or pensions."
)

# ---------------------------------------------------------------------------
# Domain agent registry
# ---------------------------------------------------------------------------

_DOMAIN_AGENTS = {
    "mortgage":   mortgage_agent,
    "investment": investment_agent,
    "pension":    pension_agent,
}


# ---------------------------------------------------------------------------
# Root orchestrator
# ---------------------------------------------------------------------------

class FinanceVerificationAgent(BaseAgent):
    """Custom orchestrator that drives the full finance verification pipeline.

    This is a manual workflow controller, not a native ADK sub-agent router.
    It emits explicit semantic Events so the trace adapter can reconstruct a
    verification-ready ExecutionTrace without relying on ADK's internal event
    structure.
    """

    # ── LLM helper ──────────────────────────────────────────────────────────

    async def _llm_call(self, system_instruction: str, user_text: str) -> str:
        """Run a single LLM call with a system instruction prepended to user content."""
        combined = f"{system_instruction.strip()}\n\n---\n\nUser query: {user_text}"
        request = LlmRequest(
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=combined)],
                )
            ]
        )
        result = ""
        async for chunk in _llm.generate_content_async(request):
            if chunk.content and chunk.content.parts:
                text = chunk.content.parts[0].text
                if text:
                    result = text.strip()
        return result

    # ── Safety check (deterministic rules, no LLM round-trip) ───────────────

    def _pattern_safety_check(self, text: str) -> tuple[str, str]:
        """Return (action, reason) using compiled regex patterns only."""
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(text):
                return "block", f"Prompt-injection pattern detected."
        for pattern in _GUARANTEED_RETURN_PATTERNS:
            if pattern.search(text):
                return "block", "Request asks for guaranteed financial outcomes."
        return "allow", "Passed all pattern checks."

    # ── Intent classification ────────────────────────────────────────────────

    async def _classify_intent(self, user_text: str) -> tuple[str, float, str]:
        """Return (domain, confidence, reasoning) using LLM structured output."""
        raw = await self._llm_call(intent_router_agent.instruction, user_text)
        try:
            # Strip any markdown code fences the LLM may add
            cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
            obj = json.loads(cleaned)
            domain = str(obj.get("domain", "general")).lower()
            if domain not in ("mortgage", "investment", "pension", "general"):
                domain = "general"
            confidence = float(obj.get("confidence", 0.5))
            reasoning = str(obj.get("reasoning", ""))
            return domain, confidence, reasoning
        except (json.JSONDecodeError, ValueError, KeyError):
            # Keyword-score fallback
            lower = user_text.lower()
            scores = {
                "mortgage":   sum(1 for kw in ("mortgage", "remortgage", "affordability", "ltv", "deposit") if kw in lower),
                "investment": sum(1 for kw in ("invest", "isa", "fund", "shares", "portfolio", "etf") if kw in lower),
                "pension":    sum(1 for kw in ("pension", "retirement", "annuity", "drawdown", "sipp") if kw in lower),
            }
            best = max(scores, key=lambda d: scores[d])
            if scores[best] == 0:
                return "general", 0.4, "Keyword fallback — no domain terms matched."
            total = sum(scores.values())
            return best, round(scores[best] / total, 2), "Keyword fallback."

    # ── Domain agent invocation ──────────────────────────────────────────────

    async def _invoke_domain_agent(self, domain: str, user_text: str) -> str:
        """Call the appropriate domain agent and return its draft response."""
        agent = _DOMAIN_AGENTS.get(domain)
        if agent is None:
            return (
                "I can help you with questions about mortgages, investments, and pensions. "
                "Could you tell me more about what you're looking for?"
            )
        return await self._llm_call(agent.instruction, user_text)

    # ── Response writer ──────────────────────────────────────────────────────

    async def _rewrite_response(self, draft: str, domain: str) -> str:
        """Rewrite draft into customer-facing guidance tone."""
        user_text = f"Domain: {domain}\n\nDraft response:\n{draft}"
        return await self._llm_call(response_writer_agent.instruction, user_text)

    # ── Event helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _make_event(
        author: str,
        invocation_id: str,
        payload: dict,
    ) -> Event:
        """Create an ADK Event carrying a compact JSON-encoded payload.

        The adapter expects deterministic JSON text so it can safely parse the
        semantic fields into ExecutionTrace metadata.
        """
        return Event(
            author=author,
            invocation_id=invocation_id,
            content={"parts": [{"text": json.dumps(payload, separators=(",", ":"))}]},
        )

    # ── Main pipeline ────────────────────────────────────────────────────────

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        invocation_id = ctx.invocation_id

        # Extract latest user message
        user_text: str = ""
        try:
            last_event = ctx.session.events[-1]
            content = last_event.content
            if hasattr(content, "parts"):
                user_text = (content.parts[0].text or "").strip()
            elif isinstance(content, dict):
                user_text = (content.get("parts", [{}])[0].get("text", "") or "").strip()
        except (IndexError, AttributeError, TypeError):
            user_text = ""

        # ── Step 1: Safety check ────────────────────────────────────────────
        yield self._make_event(
            EVENT_AUTHOR_SAFETY_CHECK_STARTED, invocation_id,
            {"summary": f"Checking query: {user_text[:80]}"},
        )

        action, reason = self._pattern_safety_check(user_text)
        prompt_injection_detected = any(
            pattern.search(user_text) for pattern in _INJECTION_PATTERNS
        )
        guaranteed_return_request = any(
            pattern.search(user_text) for pattern in _GUARANTEED_RETURN_PATTERNS
        )

        yield self._make_event(
            EVENT_AUTHOR_SAFETY_AGENT, invocation_id,
            {
                "action": action,
                "reason": reason,
                "safe": action == "allow",
                "prompt_injection_detected": prompt_injection_detected,
                "guaranteed_return_request": guaranteed_return_request,
                "safe_response_delivered": action == "block",
                "instructions_leaked": False,
                "redirection_present": action == "block",
            },
        )

        if action == "block":
            yield Event(
                author=self.name,
                invocation_id=invocation_id,
                content={"parts": [{"text": _FALLBACK_RESPONSE}]},
            )
            return

        # ── Step 2: Intent classification ───────────────────────────────────
        domain, confidence, reasoning = await self._classify_intent(user_text)

        yield self._make_event(
            EVENT_AUTHOR_INTENT_ROUTER_AGENT, invocation_id,
            {"domain": domain, "confidence": confidence, "reasoning": reasoning},
        )

        # ── Step 3: Route selection ─────────────────────────────────────────
        yield self._make_event(
            EVENT_AUTHOR_ROUTE_SELECTOR, invocation_id,
            {"selected_domain": domain},
        )

        # ── Step 4: Domain agent ────────────────────────────────────────────
        draft = await self._invoke_domain_agent(domain, user_text)

        yield self._make_event(
            f"{domain}_agent", invocation_id,
            {"domain": domain, "draft_length": len(draft)},
        )

        # ── Step 5: Response writer ─────────────────────────────────────────
        final_response = await self._rewrite_response(draft, domain)

        yield self._make_event(
            EVENT_AUTHOR_RESPONSE_WRITER_AGENT, invocation_id,
            {"domain": domain, "response_length": len(final_response)},
        )

        # ── Step 6: Deliver final response ──────────────────────────────────
        yield Event(
            author=EVENT_AUTHOR_FINAL_RESPONSE,
            invocation_id=invocation_id,
            content={"parts": [{"text": final_response}]},
        )


root_agent = FinanceVerificationAgent(
    name="finance_verification_agent",
    description=(
        "Orchestrates a multi-step financial guidance pipeline "
        "with explicit semantic events for verification."
    ),
    sub_agents=[
        safety_agent,
        intent_router_agent,
        mortgage_agent,
        investment_agent,
        pension_agent,
        response_writer_agent,
    ],
)
