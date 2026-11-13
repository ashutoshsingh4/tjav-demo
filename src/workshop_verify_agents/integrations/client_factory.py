"""Explicit factory for public asynchronous model clients."""

from __future__ import annotations

from importlib import import_module
from typing import Any, Literal

from .client_errors import ClientProviderError

ClientProvider = Literal["openai"]

_PROVIDER_MODULES = {
    "openai": ".openai_client",
}


def make_client(provider: ClientProvider) -> Any:
    """Construct a client for the explicitly selected provider, without fallback."""
    try:
        module_name = _PROVIDER_MODULES[provider]
    except KeyError:
        raise ClientProviderError("The public project supports only the 'openai' provider.") from None

    try:
        provider_module = import_module(module_name, package=__package__)
        return provider_module.make_client()
    except ClientProviderError:
        raise
    except Exception:  # noqa: BLE001 - provider errors may contain credentials.
        raise ClientProviderError(
            f"Could not construct the {provider} client; provider details are suppressed."
        ) from None