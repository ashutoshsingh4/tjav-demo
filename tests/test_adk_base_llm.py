from __future__ import annotations

import asyncio
import builtins
import importlib
from types import SimpleNamespace

import pytest
from google.adk.models.llm_request import LlmRequest
from google.genai import types

from workshop_verify_agents.integrations import adk_base_llm, adk_base_llm_smoke
from workshop_verify_agents.integrations.adk_base_llm import (
    OpenAICompatibleBaseLlm,
    OpenAICompatibleModelError,
    UnsupportedADKRequest,
)
from workshop_verify_agents.integrations.client_factory import make_client


class FakeCompletions:
    def __init__(self, *, content: str = "answer", error: Exception | None = None) -> None:
        self.content = content
        self.error = error
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


def _adapter(content: str = "answer", error: Exception | None = None):
    completions = FakeCompletions(content=content, error=error)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return OpenAICompatibleBaseLlm(model="default-model", client=client), completions


async def _collect(adapter, request, *, stream=False):
    return [response async for response in adapter.generate_content_async(request, stream=stream)]


def test_user_text_maps_to_final_adk_text_response() -> None:
    adapter, completions = _adapter("a final answer")
    request = LlmRequest(
        contents=[types.Content(role="user", parts=[types.Part.from_text(text="question")])]
    )

    responses = asyncio.run(_collect(adapter, request))

    assert completions.kwargs == {
        "model": "default-model",
        "messages": [{"role": "user", "content": "question"}],
    }
    assert len(responses) == 1
    assert responses[0].content.role == "model"
    assert responses[0].content.parts[0].text == "a final answer"
    assert responses[0].partial is False
    assert responses[0].usage_metadata is None


def test_system_and_user_messages_preserve_roles_and_request_model() -> None:
    adapter, completions = _adapter()
    request = LlmRequest(
        model="request-model",
        contents=[
            types.Content(role="user", parts=[types.Part.from_text(text="question")]),
            types.Content(role="model", parts=[types.Part.from_text(text="earlier answer")]),
        ],
        config=types.GenerateContentConfig(system_instruction="system prompt"),
    )

    asyncio.run(_collect(adapter, request))

    assert completions.kwargs == {
        "model": "request-model",
        "messages": [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "question"},
            {"role": "assistant", "content": "earlier answer"},
        ],
    }


def test_adapter_consumes_client_from_explicit_provider_factory(monkeypatch) -> None:
    provider = "openai"
    client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    selected = []
    monkeypatch.setattr(
        "workshop_verify_agents.integrations.client_factory.import_module",
        lambda name, package: selected.append(name) or SimpleNamespace(make_client=lambda: client),
    )

    provided_client = make_client(provider)
    adapter = OpenAICompatibleBaseLlm(model="model-name", client=provided_client)
    request = LlmRequest(contents=[types.Content(role="user", parts=[types.Part.from_text(text="hi")])])

    asyncio.run(_collect(adapter, request))

    assert selected == [f".{provider}_client"]
    assert provided_client is adapter.client


def test_provider_error_is_sanitized() -> None:
    adapter, _ = _adapter(error=RuntimeError("secret-token-value"))
    request = LlmRequest(contents=[types.Content(role="user", parts=[types.Part.from_text(text="hi")])])

    with pytest.raises(OpenAICompatibleModelError) as error:
        asyncio.run(_collect(adapter, request))

    assert "secret-token-value" not in str(error.value)
    assert "suppressed" in str(error.value)


def test_tool_request_fails_explicitly() -> None:
    adapter, completions = _adapter()
    request = LlmRequest.model_construct(
        contents=[types.Content(role="user", parts=[types.Part.from_text(text="hi")])],
        tools_dict={"lookup": object()},
    )

    with pytest.raises(UnsupportedADKRequest, match="tools are not supported"):
        asyncio.run(_collect(adapter, request))
    assert completions.kwargs is None


def test_function_call_part_fails_explicitly() -> None:
    adapter, completions = _adapter()
    function_call = types.Part(
        function_call=types.FunctionCall(name="lookup", args={})
    )
    request = LlmRequest(
        contents=[types.Content(role="model", parts=[function_call])]
    )

    with pytest.raises(UnsupportedADKRequest, match="text parts only"):
        asyncio.run(_collect(adapter, request))
    assert completions.kwargs is None


def test_multimodal_request_fails_explicitly() -> None:
    adapter, completions = _adapter()
    image = types.Part(inline_data=types.Blob(mime_type="image/png", data=b"image"))
    request = LlmRequest(contents=[types.Content(role="user", parts=[image])])

    with pytest.raises(UnsupportedADKRequest, match="text parts only"):
        asyncio.run(_collect(adapter, request))
    assert completions.kwargs is None


def test_structured_response_request_fails_explicitly() -> None:
    adapter, completions = _adapter()
    request = LlmRequest(
        contents=[types.Content(role="user", parts=[types.Part.from_text(text="hi")])],
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )

    with pytest.raises(UnsupportedADKRequest, match="response formats"):
        asyncio.run(_collect(adapter, request))
    assert completions.kwargs is None


def test_nondefault_generation_settings_fail_explicitly() -> None:
    adapter, completions = _adapter()
    request = LlmRequest(
        contents=[types.Content(role="user", parts=[types.Part.from_text(text="hi")])],
        config=types.GenerateContentConfig(temperature=0.2),
    )

    with pytest.raises(UnsupportedADKRequest, match="generation settings"):
        asyncio.run(_collect(adapter, request))
    assert completions.kwargs is None


def test_streaming_fails_explicitly() -> None:
    adapter, completions = _adapter()
    request = LlmRequest(contents=[types.Content(role="user", parts=[types.Part.from_text(text="hi")])])

    with pytest.raises(UnsupportedADKRequest, match="Streaming is not supported"):
        asyncio.run(_collect(adapter, request, stream=True))
    assert completions.kwargs is None


def test_adapter_import_does_not_construct_provider_client(monkeypatch) -> None:
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "openai":
            raise AssertionError(f"Adapter imported provider package {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    importlib.reload(adk_base_llm)


def test_adapter_does_not_import_client_factory() -> None:
    module = importlib.import_module("workshop_verify_agents.integrations.adk_base_llm")
    assert "make_client" not in module.__dict__


def test_deterministic_generator_never_imports_adapter(monkeypatch, tmp_path) -> None:
    original_import = builtins.__import__
    adapter_module = "workshop_verify_agents.integrations.adk_base_llm"

    def guarded_import(name, *args, **kwargs):
        if name == adapter_module:
            raise AssertionError("deterministic generator imported the optional ADK adapter")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    from workshop_verify_agents.assurance_interpretation import generate_outputs

    generate_outputs(tmp_path)
    assert (tmp_path / "tables" / "table_1_baseline_ablation.csv").exists()


def test_manual_smoke_uses_explicit_provider_and_hides_response(monkeypatch, capsys) -> None:
    completions = FakeCompletions(content="private response text")
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
        close=lambda: asyncio.sleep(0),
    )
    selected = []
    monkeypatch.setattr(
        adk_base_llm_smoke,
        "make_client",
        lambda provider: selected.append(provider) or client,
    )

    adk_base_llm_smoke.main(["--provider", "openai", "--model", "mock-model"])

    assert selected == ["openai"]
    assert completions.kwargs["model"] == "mock-model"
    captured = capsys.readouterr()
    assert "private response text" not in captured.out
    assert captured.out == "ADK provider smoke succeeded.\n"