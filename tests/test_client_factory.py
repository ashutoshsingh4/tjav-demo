from __future__ import annotations

import builtins
import importlib
from types import SimpleNamespace

import pytest

from workshop_verify_agents.integrations import client_factory, openai_client
from workshop_verify_agents.integrations.client_errors import ClientProviderError


def test_factory_import_does_not_import_provider_sdk(monkeypatch) -> None:
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "openai":
            raise AssertionError("OpenAI SDK should be imported only when selected.")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    importlib.reload(client_factory)


def test_factory_routes_to_openai_provider_only(monkeypatch) -> None:
    sentinel = object()
    imported = []
    monkeypatch.setattr(
        client_factory,
        "import_module",
        lambda name, package: imported.append(name)
        or SimpleNamespace(make_client=lambda: sentinel),
    )

    assert client_factory.make_client("openai") is sentinel
    assert imported == [".openai_client"]


def test_non_public_provider_is_rejected_without_import(monkeypatch) -> None:
    monkeypatch.setattr(
        client_factory,
        "import_module",
        lambda *args, **kwargs: pytest.fail("Unsupported providers must not be imported."),
    )

    with pytest.raises(ClientProviderError, match="only the 'openai' provider"):
        client_factory.make_client("unsupported")


def test_openai_key_is_required(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ClientProviderError, match="OPENAI_API_KEY"):
        openai_client.make_client()


def test_openai_client_uses_environment_key_without_exposing_it(monkeypatch) -> None:
    secret = "test-key-never-printed"
    constructed = {}
    sentinel = object()

    def make_async_client(**kwargs):
        constructed.update(kwargs)
        return sentinel

    monkeypatch.setenv("OPENAI_API_KEY", secret)
    monkeypatch.setitem(
        __import__("sys").modules,
        "openai",
        SimpleNamespace(AsyncOpenAI=make_async_client),
    )

    assert openai_client.make_client() is sentinel
    assert constructed == {"api_key": secret}
