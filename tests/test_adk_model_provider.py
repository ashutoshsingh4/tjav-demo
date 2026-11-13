from __future__ import annotations

import builtins
import importlib
import sys
from types import ModuleType, SimpleNamespace

import pytest

from workshop_verify_agents.integrations.client_errors import ClientProviderError

_ADK_PACKAGE = "workshop_verify_agents.adk_runtime"
_AGENT_MODULES = (
    "safety_agent",
    "intent_router_agent",
    "mortgage_agent",
    "investment_agent",
    "pension_agent",
    "response_writer_agent",
)


def _load_current_module(name: str) -> ModuleType:
    module_name = f"{_ADK_PACKAGE}.{name}"
    module = sys.modules.get(module_name)
    if module is None:
        return importlib.import_module(module_name)
    return importlib.reload(module)


def test_existing_adk_tree_uses_openai_provider_and_model(monkeypatch) -> None:
    provider = "openai"
    monkeypatch.setenv("MODEL_PROVIDER", provider)
    monkeypatch.setenv("MODEL_NAME", "mock-model")

    model_provider = _load_current_module("model_provider")
    client = SimpleNamespace()
    selected_providers = []
    model_provider.make_client = (
        lambda selected: selected_providers.append(selected) or client
    )

    original_import = builtins.__import__

    def reject_legacy_model_import(name, *args, **kwargs):
        if name.startswith("model."):
            raise AssertionError("ADK runtime imported an unexpected legacy model module")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_legacy_model_import)

    agents = {
        name: _load_current_module(name)
        for name in _AGENT_MODULES
    }
    root_agent_module = _load_current_module("root_agent")
    runner_module = _load_current_module("runner")

    model = root_agent_module._llm
    assert model.model == "mock-model"
    assert model.client is client
    assert selected_providers == [provider]
    assert runner_module.root_agent is root_agent_module.root_agent
    assert root_agent_module.root_agent.sub_agents == [
        agents["safety_agent"].safety_agent,
        agents["intent_router_agent"].intent_router_agent,
        agents["mortgage_agent"].mortgage_agent,
        agents["investment_agent"].investment_agent,
        agents["pension_agent"].pension_agent,
        agents["response_writer_agent"].response_writer_agent,
    ]
    expected_agents = [
        getattr(agents[name], name)
        for name in _AGENT_MODULES
    ]
    assert all(agent.model is model for agent in expected_agents)


@pytest.mark.parametrize(
    ("provider", "model_name", "message"),
    [
        ("", "mock-model", "MODEL_PROVIDER"),
        ("openai", "", "MODEL_NAME"),
        ("unsupported", "mock-model", "MODEL_PROVIDER"),
    ],
)
def test_missing_or_invalid_runtime_configuration_fails_before_client_creation(
    monkeypatch,
    provider,
    model_name,
    message,
) -> None:
    monkeypatch.setenv("MODEL_PROVIDER", provider)
    monkeypatch.setenv("MODEL_NAME", model_name)
    model_provider = _load_current_module("model_provider")
    monkeypatch.setattr(
        model_provider,
        "make_client",
        lambda provider: pytest.fail(
            f"invalid configuration must not construct the {provider} client"
        ),
    )

    with pytest.raises(ClientProviderError, match=message):
        model_provider.get_llm()
