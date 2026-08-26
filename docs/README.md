# Reviewer Guide

The deterministic path is the canonical reproduction route:

```text
uv sync
uv run python -m workshop_verify_agents.demo_offline_verification
uv run pytest -q
```

The demo verifies the method rather than benchmarking a language model. Its five scenarios use deterministic conversations, supplied journey-stage labels, and mocked turn-level quality scores.

The optional ADK path uses `OPENAI_API_KEY` from `.env` and produces live runtime responses and normalized traces. It is non-deterministic and may incur API costs.

## Reading order

1. `../README.md`
2. `architecture.md`
3. `scenarios.md`
4. `../src/workshop_verify_agents/verification/`
