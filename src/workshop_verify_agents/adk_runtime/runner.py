"""ADK runtime runner for workshop verification.

This module provides:
1) A reusable ``ADKConversationRunner`` that supports multi-turn session reuse.
2) A backward-compatible ``run_adk_conversation`` helper for existing single-turn
     CLI/notebook flows.

Design boundary:
- This runner is the execution host: it manages ADK session/runner lifecycle,
    collects raw ADK events, and normalises events into ``ExecutionTrace``.
- Business workflow logic remains in ``root_agent.py``.

Current output model:
- Each invocation returns a per-turn ``ExecutionTrace`` normalised from events
    emitted during that invocation.
- Conversation-level evidence packing across turns is future work.
"""

from __future__ import annotations

import asyncio
from typing import Any

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from .adk_trace_adapter import normalise_adk_events_to_execution_trace
from .root_agent import root_agent
from workshop_verify_agents.verification.trace_schema import ExecutionTrace

_APP_NAME = "workshop_verify_agents_adk"
_USER_ID = "demo_user"


# ---------------------------------------------------------------------------
# Reusable multi-turn runner
# ---------------------------------------------------------------------------


class ADKConversationRunner:
    """Reusable ADK conversation runner with session reuse by conversation ID.

    ``conversation_id`` maps directly to ADK ``session_id``.
    Reusing the same ``conversation_id`` across turns reuses the same ADK
    session so ADK-managed context can accumulate across turns.
    """

    def __init__(
        self,
        app_name: str = _APP_NAME,
        user_id: str = _USER_ID,
        session_service: InMemorySessionService | None = None,
    ) -> None:
        self._app_name = app_name
        self._user_id = user_id
        self._session_service = session_service or InMemorySessionService()
        self._runner = Runner(
            app_name=self._app_name,
            agent=root_agent,
            session_service=self._session_service,
        )
        self._known_sessions: set[str] = set()

    async def ensure_session(self, session_id: str) -> None:
        """Create a session if this runner has not yet seen ``session_id``."""
        if session_id in self._known_sessions:
            return

        await self._session_service.create_session(
            app_name=self._app_name,
            user_id=self._user_id,
            session_id=session_id,
        )
        self._known_sessions.add(session_id)

    async def run_turn(
        self,
        query: str,
        conversation_id: str,
    ) -> tuple[str, list[Any], ExecutionTrace]:
        """Run one turn and return ``(final_response, raw_events, trace)``.

        The returned trace contains only events observed for this invocation.
        ADK session history is retained by the in-memory session service when
        the same ``conversation_id`` is reused.
        """
        await self.ensure_session(conversation_id)
        message = self._build_user_message(query)
        raw_events = await self._collect_events(conversation_id, message)
        final_response = _extract_final_response(raw_events)
        trace = self._normalise_trace(raw_events, conversation_id)
        return final_response, raw_events, trace

    def run_turn_sync(
        self,
        query: str,
        conversation_id: str,
    ) -> tuple[str, ExecutionTrace]:
        """Synchronous wrapper returning ``(final_response, trace)``."""
        final_response, _raw_events, trace = asyncio.run(
            self.run_turn(query, conversation_id)
        )
        return final_response, trace

    def reset_session(self, conversation_id: str) -> None:
        """Forget local tracking for a conversation in this runner instance.

        This does not delete server-side/session-service history; it only
        removes local knowledge in this runner object.
        """
        self._known_sessions.discard(conversation_id)

    def _build_user_message(self, query: str) -> types.Content:
        return types.Content(
            role="user",
            parts=[types.Part.from_text(text=query)],
        )

    async def _collect_events(self, session_id: str, message: types.Content) -> list[Any]:
        raw_events: list[Any] = []
        async for event in self._runner.run_async(
            session_id=session_id,
            user_id=self._user_id,
            new_message=message,
        ):
            raw_events.append(event)
        return raw_events

    def _normalise_trace(self, events: list[Any], conversation_id: str) -> ExecutionTrace:
        return normalise_adk_events_to_execution_trace(events, conversation_id)


# ---------------------------------------------------------------------------
# Public compatibility API
# ---------------------------------------------------------------------------

def run_adk_conversation(
    query: str,
    conversation_id: str,
) -> tuple[str, ExecutionTrace]:
    """Run one ADK turn using the legacy one-shot helper API.

    This function preserves existing behavior for CLI/notebook flows by
    creating a fresh ``ADKConversationRunner`` per call.

    Parameters
    ----------
    query:
        The customer query to process.
    conversation_id:
        Used as both the ADK session ID and the ``ExecutionTrace.conversation_id``.

    Returns
    -------
    tuple[str, ExecutionTrace]
        ``(final_response, execution_trace)`` where ``final_response`` is the
        customer-facing text and ``execution_trace`` contains all normalised
        verification events for this invocation.

    Notes
    -----
    For multi-turn session reuse, instantiate ``ADKConversationRunner`` and
    call ``run_turn_sync`` repeatedly with the same ``conversation_id``.
    """
    runner = ADKConversationRunner()
    return runner.run_turn_sync(query, conversation_id)


def demo_multi_turn_session() -> list[tuple[str, ExecutionTrace]]:
    """Small illustrative helper for two turns on one shared conversation."""
    runner = ADKConversationRunner()
    conversation_id = "demo-conversation-1"

    results: list[tuple[str, ExecutionTrace]] = []
    results.append(
        runner.run_turn_sync("I'm a first-time buyer.", conversation_id)
    )
    results.append(
        runner.run_turn_sync(
            "What information will lenders check?",
            conversation_id,
        )
    )
    return results


# ---------------------------------------------------------------------------
# Final response extraction
# ---------------------------------------------------------------------------

def _extract_final_response(events: list[Any]) -> str:
    """Return the last non-empty plain-text response from the root agent.

    Iterates in reverse so that the last event with a non-JSON text
    payload from the root orchestrator is selected.
    """
    for event in reversed(events):
        author = _safe_str(getattr(event, "author", None))
        if author == "finance_verification_agent":
            text = _extract_event_text(event)
            if text:
                return text

    # Fallback: return the last text-bearing event from any author
    for event in reversed(events):
        text = _extract_event_text(event)
        if text and not text.strip().startswith("{"):
            return text

    return "(no response generated)"


def _extract_event_text(event: Any) -> str:
    """Safely extract text from an ADK event's content."""
    try:
        content = getattr(event, "content", None)
        if content is None:
            return ""
        if hasattr(content, "parts"):
            for part in (content.parts or []):
                text = getattr(part, "text", None)
                if text:
                    return str(text)
        if isinstance(content, dict):
            for part in content.get("parts", []):
                if isinstance(part, dict):
                    text = part.get("text")
                    if text:
                        return str(text)
    except Exception:
        pass
    return ""


def _safe_str(value: Any) -> str:
    try:
        return str(value) if value is not None else ""
    except Exception:
        return ""
