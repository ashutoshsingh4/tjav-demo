"""V0 experimental ADK BaseLlm adapter for OpenAI-compatible async clients."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import Field


class UnsupportedADKRequest(ValueError):
    """The request uses a feature not supported by this text-only V0 adapter."""


class OpenAICompatibleModelError(RuntimeError):
    """A sanitized failure from an OpenAI-compatible provider request."""


def _text_from_part(part: types.Part) -> str:
    fields_set = getattr(part, "model_fields_set", set())
    unsupported_fields = fields_set - {"text"}
    if unsupported_fields:
        raise UnsupportedADKRequest(
            "This ADK adapter supports text parts only; non-text content was provided."
        )
    text = part.text
    if not isinstance(text, str):
        raise UnsupportedADKRequest("This ADK adapter requires text content parts.")
    return text


def _content_to_text(content: types.Content) -> str:
    if not content.parts:
        raise UnsupportedADKRequest("This ADK adapter requires non-empty text content.")
    return "".join(_text_from_part(part) for part in content.parts)


def _system_instruction_to_text(instruction: Any) -> str | None:
    if instruction is None:
        return None
    if isinstance(instruction, str):
        return instruction
    if isinstance(instruction, types.Content):
        return _content_to_text(instruction)
    if isinstance(instruction, types.Part):
        return _text_from_part(instruction)
    if isinstance(instruction, list):
        if not all(isinstance(part, (str, types.Part)) for part in instruction):
            raise UnsupportedADKRequest(
                "This ADK adapter supports text-only system instructions."
            )
        return "".join(part if isinstance(part, str) else _text_from_part(part) for part in instruction)
    raise UnsupportedADKRequest("This ADK adapter supports text-only system instructions.")


def _contains_config_value(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_config_value(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_config_value(item) for item in value)
    return value is not None


def _request_to_messages(request: LlmRequest) -> list[dict[str, str]]:
    config = request.config
    if request.tools_dict or config.tools:
        raise UnsupportedADKRequest("ADK tools are not supported by this adapter version.")
    if config.response_schema is not None or config.response_json_schema is not None:
        raise UnsupportedADKRequest("Structured response schemas are not supported by this adapter version.")
    if config.response_mime_type not in (None, "text/plain"):
        raise UnsupportedADKRequest("Non-text response formats are not supported by this adapter version.")
    config_values = config.model_dump(exclude_none=True, exclude_defaults=True)
    unsupported_config = set(config_values) - {
        "system_instruction",
        "labels",
        "response_mime_type",
    }
    if unsupported_config:
        raise UnsupportedADKRequest(
            "Non-default ADK generation settings are not supported by this adapter version."
        )
    labels = config_values.get("labels", {})
    if set(labels) - {"adk_agent_name"}:
        raise UnsupportedADKRequest("Custom ADK labels are not supported by this adapter version.")
    live_config = request.live_connect_config.model_dump(
        exclude_none=True,
        exclude_defaults=True,
    )
    if _contains_config_value(live_config):
        raise UnsupportedADKRequest("Live-session requests are not supported by this adapter version.")

    messages: list[dict[str, str]] = []
    system_instruction = _system_instruction_to_text(config.system_instruction)
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})

    for content in request.contents:
        role = content.role or "user"
        openai_role = {"user": "user", "model": "assistant"}.get(role)
        if openai_role is None:
            raise UnsupportedADKRequest(f"ADK content role {role!r} is not supported.")
        messages.append({"role": openai_role, "content": _content_to_text(content)})

    if not messages:
        raise UnsupportedADKRequest("The ADK request contains no text messages.")
    return messages


class OpenAICompatibleBaseLlm(BaseLlm):
    """Text-only ADK model adapter consuming an injected async OpenAI client."""

    client: Any = Field(exclude=True, repr=False)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        if stream:
            raise UnsupportedADKRequest("Streaming is not supported by this adapter version.")

        messages = _request_to_messages(llm_request)
        model_name = llm_request.model or self.model
        try:
            response = await self.client.chat.completions.create(
                model=model_name,
                messages=messages,
            )
        except Exception:  # noqa: BLE001 - provider exceptions may expose credentials.
            raise OpenAICompatibleModelError(
                "The OpenAI-compatible provider request failed; details are suppressed."
            ) from None

        choices = getattr(response, "choices", None)
        message = getattr(choices[0], "message", None) if choices else None
        text = getattr(message, "content", None)
        if not isinstance(text, str):
            raise UnsupportedADKRequest(
                "The provider response did not contain a single text result."
            )

        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part.from_text(text=text)],
            ),
            partial=False,
        )