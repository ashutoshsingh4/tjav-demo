"""OpenAI model configuration for the optional ADK demonstration."""

from __future__ import annotations

import os

from dotenv import find_dotenv, load_dotenv

try:
    import truststore
except ModuleNotFoundError:
    truststore = None

if truststore is not None:
    # Use the operating-system certificate store without disabling TLS checks.
    truststore.inject_into_ssl()

from google.adk.models.lite_llm import LiteLlm, LiteLLMClient
from pydantic import Field

load_dotenv(find_dotenv())


class SerializableLiteLlm(LiteLlm):
    """Exclude LiteLLM's runtime client from ADK model serialization."""

    llm_client: LiteLLMClient = Field(default_factory=LiteLLMClient, exclude=True)


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if not OPENAI_API_KEY:
    raise OSError(
        "OPENAI_API_KEY is required for the optional ADK demo. "
        "Copy sample.env to .env and add your key."
    )

llm = SerializableLiteLlm(
    model=f"openai/{OPENAI_MODEL}",
    api_key=OPENAI_API_KEY,
)