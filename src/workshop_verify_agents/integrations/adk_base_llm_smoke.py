"""OPTIONAL EXPERIMENTAL ADK INTEGRATION CHECK; not an IAB reproduction."""

from __future__ import annotations

import argparse
import asyncio
from uuid import uuid4

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from .adk_base_llm import OpenAICompatibleBaseLlm
from .client_factory import make_client

_APP_NAME = "optional_provider_bridge_smoke"
_USER_ID = "provider_bridge_smoke_user"


async def _run(provider: str, model_name: str) -> None:
    client = make_client(provider)
    try:
        agent = Agent(
            name="provider_bridge_smoke_agent",
            model=OpenAICompatibleBaseLlm(model=model_name, client=client),
            instruction="Reply with a brief acknowledgement.",
        )
        session_id = str(uuid4())
        session_service = InMemorySessionService()
        await session_service.create_session(
            app_name=_APP_NAME,
            user_id=_USER_ID,
            session_id=session_id,
        )
        runner = Runner(
            app_name=_APP_NAME,
            agent=agent,
            session_service=session_service,
        )
        response_seen = False
        async for event in runner.run_async(
            user_id=_USER_ID,
            session_id=session_id,
            new_message=types.Content(
                role="user",
                parts=[types.Part.from_text(text="Please acknowledge this request.")],
            ),
        ):
            if event.author == agent.name and event.content:
                response_seen = response_seen or any(
                    bool(part.text and part.text.strip())
                    for part in event.content.parts or []
                )
        if not response_seen:
            raise RuntimeError("No final text response was observed.")
    finally:
        await client.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("openai",), required=True)
    parser.add_argument("--model", required=True, help="Provider model identifier")
    args = parser.parse_args(argv)
    try:
        asyncio.run(_run(args.provider, args.model))
    except Exception:  # noqa: BLE001 - do not print ADK/provider exception details.
        parser.exit(1, "ADK provider smoke failed; provider details are suppressed.\n")
    print("ADK provider smoke succeeded.")


if __name__ == "__main__":
    main()