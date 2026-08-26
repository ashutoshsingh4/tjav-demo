# Agent Verification Demo

This supplementary package reproduces the workshop demonstrator for verifying enterprise conversational agents.

The demo has two complementary lanes:

- **Behaviour verification:** runtime events are normalized into an `ExecutionTrace`, mapped to business signals, checked against applicable controls, and converted into evidence.
- **Journey-aware outcome verification:** deterministic conversation exchanges use supplied journey stages and quality scores to compare simple and stage-weighted outcomes.

The offline path is deterministic and requires no API key. The optional ADK path runs the same verification pipeline over live OpenAI-backed agent events.

## Quickstart

Requires Python 3.10-3.13 and [uv](https://docs.astral.sh/uv/).

```text
uv sync
uv run python -m workshop_verify_agents.app --mode synthetic --query "How does mortgage affordability work?"
uv run python -m workshop_verify_agents.demo_offline_verification
uv run pytest -q
```

The five deterministic scenarios are listed in `docs/scenario_index.md`.

## Optional OpenAI run

The live path is optional and incurs OpenAI API usage costs. Create a local environment file from the template:

PowerShell:

```powershell
Copy-Item sample.env .env
```

Git Bash:

```bash
cp sample.env .env
```

Set `OPENAI_API_KEY` in `.env`, then run:

```text
uv run python -m workshop_verify_agents.app --mode adk --query "How does mortgage affordability work?"
```

`OPENAI_MODEL` defaults to `gpt-4o-mini`. Never commit `.env` or an API key.

### TLS certificate troubleshooting

If the request fails with `CERTIFICATE_VERIFY_FAILED`, Python does not trust
the certificate presented by the local HTTPS proxy. First ensure your
organization's root CA is installed in the Windows certificate store; the demo
uses that store through `truststore`. If the CA is supplied as a PEM bundle,
set `SSL_CERT_FILE` in `.env` to its absolute path, for example:

```env
SSL_CERT_FILE=C:/path/to/corporate-root-ca-bundle.pem
```

Do not set certificate verification to `false` and do not work around this
error by disabling TLS. The LiteLLM remote cost-map warning is harmless; the
actual API request must still be able to establish a verified HTTPS connection.

## Design boundary

The synthetic and ADK runtimes both produce the shared `ExecutionTrace` representation. The offline journey scores and stage labels are deterministic workshop inputs; the live ADK path does not derive quality scores from model output.

## Layout

```text
src/model/                         OpenAI model configuration for ADK
src/workshop_verify_agents/        runtime, verification, journey, and scenarios
tests/                             unit and end-to-end tests
docs/                              concise architecture and scenario notes
```
