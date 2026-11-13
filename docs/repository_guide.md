# Repository Guide: Navigation And Ownership

This document is navigation-focused. It explains where things live, which files are entrypoints, and how paper concepts map to code.

Standard operating statement:

Online CLI flow is behaviour-only.
Offline verifier provides conversation-level unified behaviour and outcome assessment.

## 1. Folder Responsibility Matrix

| Path | Responsibility | Produces | Used By |
|---|---|---|---|
| [src/workshop_verify_agents/adk_runtime](src/workshop_verify_agents/adk_runtime) | ADK runtime execution, session reuse, event normalization | ADK responses + normalized ExecutionTrace | Optional live ADK lane |
| [src/workshop_verify_agents/synthetic_runtime](src/workshop_verify_agents/synthetic_runtime) | Deterministic synthetic orchestrator runtime | Synthetic responses + ExecutionTrace | Default online lane and offline demos |
| [src/workshop_verify_agents/verification](src/workshop_verify_agents/verification) | Signal extraction, evidence construction, assessment policy, lane orchestrators | Business signals, evidence, assessments | App, offline demo, notebooks |
| [src/workshop_verify_agents/journey](src/workshop_verify_agents/journey) | Stage taxonomy, classification, weighted scoring | Journey labels, weighted outcome comparisons | Offline lane, journey demos |
| [src/workshop_verify_agents/examples](src/workshop_verify_agents/examples) | Scenario definitions for synthetic research evaluation | Conversations, expected stages, mocked quality scores | Offline demo, notebooks, scenario reviews |
| [src/workshop_verify_agents/notebooks](src/workshop_verify_agents/notebooks) | Optional demonstrations of contribution-specific flows | Notebook outputs and analysis views | Workshop preparation and extended review |
| [src/workshop_verify_agents/config](src/workshop_verify_agents/config) | Configuration and specification artifacts | Signal and journey rule specs | Verification implementation and documentation |
| [docs](docs) | Reviewer and architecture documentation | Quickstart, navigation, research context, technical architecture | New contributors and workshop reviewers |
| [examples](examples) | Repository-level scenario/evidence artifacts | JSON scenario and expected-output assets | Paper and review appendices |

## 2. Key Runtime Entry Points

- Main CLI entrypoint: [src/workshop_verify_agents/app.py](src/workshop_verify_agents/app.py)
- ADK runner and reusable session host: [src/workshop_verify_agents/adk_runtime/runner.py](src/workshop_verify_agents/adk_runtime/runner.py)
- Synthetic orchestrator: [src/workshop_verify_agents/synthetic_runtime/orchestrator.py](src/workshop_verify_agents/synthetic_runtime/orchestrator.py)
- Online turn verification API: [src/workshop_verify_agents/verification/online_verifier.py](src/workshop_verify_agents/verification/online_verifier.py)
- Offline conversation verification API: [src/workshop_verify_agents/verification/offline_verifier.py](src/workshop_verify_agents/verification/offline_verifier.py)
- Offline verification demo: [src/workshop_verify_agents/demo_offline_verification.py](src/workshop_verify_agents/demo_offline_verification.py)
- ADK verification demo: [src/workshop_verify_agents/demo_adk_verification.py](src/workshop_verify_agents/demo_adk_verification.py)

## 3. Scenario Suite Overview

Core scenario source:

- [src/workshop_verify_agents/examples/conversations.py](src/workshop_verify_agents/examples/conversations.py)

The offline demonstrator currently registers 15 scenarios spanning nominal
execution, effective and ineffective policy controls, repeated routing/loop
risk, recovered and unrecovered tool failures, omitted escalation, and
critical-stage outcome weakness. The authoritative scenario list and current
behaviour/outcome/unified decisions are in [docs/scenario_index.md](scenario_index.md).

Supporting review assets:

- [docs/scenario_index.md](docs/scenario_index.md)
- [docs/pipeline_examples.md](docs/pipeline_examples.md)
- [examples/verification_scenarios.json](examples/verification_scenarios.json)
- [examples/pipeline_expected_outputs.json](examples/pipeline_expected_outputs.json)

Interpretation note:

- Scenarios are synthetic, deterministic, and author-constructed. Journey
  stages and quality scores are supplied fixtures. The 15 cases exercise
  trace-derived policy, routing, recovery, escalation, and operational evidence
  as well as journey-aware outcomes; they are not a live-agent benchmark.

## 4. Read Order And Run Order

Read in this order for a sub-10-minute review:

1. [README.md](README.md) for high-level architecture and contribution summary.
2. [docs/repository_guide.md](docs/repository_guide.md) for reviewer-oriented orientation (this document).
3. [docs/research_context.md](docs/research_context.md) for research rationale and limitations.
4. [docs/architecture_review.md](docs/architecture_review.md) for as-built runtime and module mapping.
5. [src/workshop_verify_agents/demo_offline_verification.py](src/workshop_verify_agents/demo_offline_verification.py) for a concrete end-to-end offline example.

Run in this order:

First command (fastest way to see real output without ADK setup):

```bash
uv run python -m workshop_verify_agents.app --mode synthetic --query "How does mortgage affordability work?"
```

Second command (to see conversation-level unified behaviour + journey-aware outcome):

```bash
uv run python -m workshop_verify_agents.demo_offline_verification
```

Run the complete 15-scenario report and table generator:

```bash
uv run python -m workshop_verify_agents.assurance_interpretation --output-dir <output-directory>
```

Optional ADK conversation-level verification (requires environment setup; outcome scores and stage labels remain fixtures):

```bash
uv run python -m workshop_verify_agents.demo_adk_verification
```

Optional ADK mode command (requires environment setup):

```bash
uv run python -m workshop_verify_agents.app --mode adk --query "How does mortgage affordability work?"
```

## 5. Paper-To-Code Mapping

| Paper Concept | Code Anchor |
|---|---|
| Problem framing: outcome-only evaluation is insufficient | [docs/research_context.md](docs/research_context.md#L3) |
| Contribution 1: trace-derived behaviour verification | [src/workshop_verify_agents/verification/online_verifier.py](src/workshop_verify_agents/verification/online_verifier.py), [src/workshop_verify_agents/verification/signal_extractor.py](src/workshop_verify_agents/verification/signal_extractor.py), [src/workshop_verify_agents/verification/evidence_builder.py](src/workshop_verify_agents/verification/evidence_builder.py), [src/workshop_verify_agents/verification/verification_assessor.py](src/workshop_verify_agents/verification/verification_assessor.py) |
| Contribution 2: journey-aware outcome verification | [src/workshop_verify_agents/journey/journey_classifier.py](src/workshop_verify_agents/journey/journey_classifier.py), [src/workshop_verify_agents/journey/journey_weighted_scorer.py](src/workshop_verify_agents/journey/journey_weighted_scorer.py), [src/workshop_verify_agents/verification/journey_outcome_adapter.py](src/workshop_verify_agents/verification/journey_outcome_adapter.py) |
| Policy-aware behaviour verification | [src/workshop_verify_agents/verification/policy_schema.py](src/workshop_verify_agents/verification/policy_schema.py), [src/workshop_verify_agents/verification/policy_verifier.py](src/workshop_verify_agents/verification/policy_verifier.py), [src/workshop_verify_agents/verification/evidence_builder.py](src/workshop_verify_agents/verification/evidence_builder.py) |
| Unified assessment across behaviour and outcome lanes | [src/workshop_verify_agents/verification/offline_verifier.py](src/workshop_verify_agents/verification/offline_verifier.py), [src/workshop_verify_agents/verification/verification_assessor.py](src/workshop_verify_agents/verification/verification_assessor.py) |
| Runtime execution sources (synthetic + ADK) | [src/workshop_verify_agents/synthetic_runtime/orchestrator.py](src/workshop_verify_agents/synthetic_runtime/orchestrator.py), [src/workshop_verify_agents/adk_runtime/runner.py](src/workshop_verify_agents/adk_runtime/runner.py), [src/workshop_verify_agents/adk_runtime/adk_trace_adapter.py](src/workshop_verify_agents/adk_runtime/adk_trace_adapter.py) |
| Reproducible evaluation scenarios | [src/workshop_verify_agents/examples/conversations.py](src/workshop_verify_agents/examples/conversations.py), [docs/scenario_index.md](docs/scenario_index.md) |

## 6. Notebook Alignment Status

- [src/workshop_verify_agents/notebooks/01_trace_to_signal_demo.ipynb](src/workshop_verify_agents/notebooks/01_trace_to_signal_demo.ipynb): demonstrates behaviour verification flow from trace to evidence and assessment.
- [src/workshop_verify_agents/notebooks/02_journey_aware_verification_demo.ipynb](src/workshop_verify_agents/notebooks/02_journey_aware_verification_demo.ipynb): demonstrates journey-aware outcome verification and weighted interpretation.

Both notebooks remain relevant. A future unified notebook can be considered later, but is not required for the current repository architecture.

---

Quick reviewer summary:

- If you only have 3 minutes, read [README.md](README.md) and run the first command above.
- If you have 10 minutes, use the read and run order in this guide, then inspect [docs/architecture_review.md](docs/architecture_review.md).
