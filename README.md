# TJAV — Trajectory and Journey-Aware Verifier

TJAV is a research demonstrator for auditable verification of conversational
agents. It combines trace-derived behaviour evidence with journey-aware outcome
evidence. The reported experiment is deterministic and offline.

## What is included

- A deterministic synthetic runtime that needs no API key or external service.
- An optional Google ADK runtime using OpenAI as its model provider.
- A shared verification pipeline for traces, signals, evidence, and assessments.
- Fifteen controlled, author-constructed scenarios and a report generator.
- Tests and the accepted paper source/assets.

The scenarios use supplied journey-stage labels and quality scores. They test
implemented evidence rules; they are not a representative sample, live-agent
benchmark, or production validation.

## Install

Python 3.10–3.13 and [uv](https://docs.astral.sh/uv/) are supported.

```shell
uv sync
```

For the optional ADK/OpenAI runtime:

```shell
uv sync --extra adk
```

Set `MODEL_PROVIDER=openai`, `MODEL_NAME` to an OpenAI-supported model, and
`OPENAI_API_KEY` in the process environment before using ADK mode. The project
does not store credentials.

## Run

Deterministic synthetic runtime:

```shell
uv run python -m workshop_verify_agents.app --mode synthetic --query "How does mortgage affordability work?"
```

Optional ADK runtime:

```shell
uv run python -m workshop_verify_agents.app --mode adk --query "How does mortgage affordability work?"
```

Generate the reported 15-scenario outputs:

```shell
uv run python -m workshop_verify_agents.assurance_interpretation --output-dir <output-directory>
```

Run tests:

```shell
uv run pytest -q
```

## Project layout

- `src/workshop_verify_agents/`: runtimes and shared verification implementation.
- `tests/`: deterministic, ADK adapter, and mocked OpenAI-provider tests.
- `docs/`: architecture, evidence policy, scenario index, and research context.
- `docs/paper/`: accepted paper source and its assets.

The optional live-provider path is separate from the deterministic reported
results. The public ADK integration supports text-only requests; streaming,
tools, multimodal content, structured output, and non-default generation
settings are not supported by its current adapter.

## License and third-party material

TJAV project code is intended to be released under the MIT License; replace
the copyright-holder placeholder in `LICENSE` with the authorized rights
holder before publication. Third-party paper templates, figures, dependencies,
and other included material may have separate terms and are not relicensed by
the project license.
