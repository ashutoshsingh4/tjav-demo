"""Public OpenAI provider; credentials come only from the process environment."""

from __future__ import annotations

import os
from typing import Any

from .client_errors import ClientProviderError


def make_client() -> Any:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ClientProviderError("Set OPENAI_API_KEY to use the OpenAI provider.")

    try:
        import openai
    except ImportError:
        raise ClientProviderError(
            "The OpenAI package is unavailable in this environment."
        ) from None

    try:
        return openai.AsyncOpenAI(api_key=api_key)
    except Exception:  # noqa: BLE001 - client errors may echo credentials.
        raise ClientProviderError(
            "Could not construct the OpenAI client; provider details are suppressed."
        ) from None