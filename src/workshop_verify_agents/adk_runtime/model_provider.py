"""Re-exports the shared LLM instance from the shared model package.

All ADK runtime agents obtain their model through this single function so that
credentials and model configuration remain in one place (model/models.py).
"""

from __future__ import annotations

from model.models import llm


def get_llm():
    """Return the shared ADK-compatible LLM instance."""
    return llm
