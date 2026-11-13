"""Build the shared ADK model from the explicitly selected client provider."""

from __future__ import annotations

import os
from functools import lru_cache

from workshop_verify_agents.integrations.adk_base_llm import OpenAICompatibleBaseLlm
from workshop_verify_agents.integrations.client_errors import ClientProviderError
from workshop_verify_agents.integrations.client_factory import ClientProvider, make_client


def _configured_provider() -> ClientProvider:
    provider = os.environ.get("MODEL_PROVIDER", "").strip().lower()
    if provider == "openai":
        return "openai"
    raise ClientProviderError(
        "Set MODEL_PROVIDER to 'openai' to use the public ADK runtime."
    )


@lru_cache(maxsize=1)
def _build_llm(provider: ClientProvider, model_name: str) -> OpenAICompatibleBaseLlm:
    return OpenAICompatibleBaseLlm(
        model=model_name,
        client=make_client(provider),
    )


def get_llm() -> OpenAICompatibleBaseLlm:
    """Return the cached ADK model configured by MODEL_PROVIDER and MODEL_NAME."""
    model_name = os.environ.get("MODEL_NAME", "").strip()
    if not model_name:
        raise ClientProviderError(
            "Set MODEL_NAME to the model identifier required by the selected provider."
        )
    return _build_llm(_configured_provider(), model_name)
