# workshop_verify_agents

Research and demo package for the NeurIPS 2026 workshop topic:
verifying enterprise conversational agents with trace-derived evidence and
journey-aware interpretation.

## What This Module Demonstrates

1. Trace-derived verification:
    Execution behaviour is normalized into an ExecutionTrace, converted to
     business signals, transformed into evidence, and assessed.

2. Journey-aware outcome interpretation:
     Multi-turn conversations are classified by journey stage and scored with
     stage-aware weighting to avoid false confidence from simple averages.

## Runtime Architecture

app.py is the CLI and demo entrypoint. It supports two runtime modes:

1. Synthetic runtime:
    deterministic orchestration in synthetic_runtime/ for reproducible research scenarios.

2. ADK runtime:
     real ADK execution host in adk_runtime/, emitting an ADK event stream that
     is normalized into ExecutionTrace.

Both runtime modes feed the same verification pipeline in verification/.
The reported 15-scenario path is deterministic and offline. The optional ADK
runtime shares that evaluation layer but uses an explicitly selected external
model provider; neither live provider generates the paper results.

## Repository Structure

src/workshop_verify_agents/
- app.py: CLI/demo entrypoint
- adk_runtime/: ADK execution runtime (session management, runner lifecycle,
    event collection, trace normalization)
- synthetic_runtime/: deterministic synthetic runtime for controlled scenarios
- verification/: trace-derived behaviour verification stack
- journey/: journey-aware outcome verification framework
- examples/: 15 deterministic, author-constructed scenarios and expected evidence
- notebooks/: reproducible demonstrations for workshop experiments
- config/: rules, weights, and future externalization assets

## ADK Runtime: Single-Turn And Multi-Turn Usage

Backward-compatible single-turn helper:

- run_adk_conversation(query, conversation_id) -> tuple[str, ExecutionTrace]
- Used by app.py in current CLI flows.
- Behavior remains one-shot per invocation for compatibility.

Reusable multi-turn runner:

- ADKConversationRunner in adk_runtime/runner.py
- conversation_id maps directly to ADK session_id
- Reusing the same conversation_id across turns reuses ADK session context
- Each turn returns a per-turn ExecutionTrace normalized via
    adk_trace_adapter.py

Minimal multi-turn usage pattern:

```python
from workshop_verify_agents.adk_runtime.runner import ADKConversationRunner

runner = ADKConversationRunner()
conversation_id = "demo-conversation-1"

turn1_response, turn1_trace = runner.run_turn_sync(
        "I'm a first-time buyer.",
        conversation_id,
)
turn2_response, turn2_trace = runner.run_turn_sync(
        "What information will lenders check?",
        conversation_id,
)
```

Why this matters:

- Multi-turn conversational-agent verification needs persistent session context.
- Future journey-aware verification depends on coherent cross-turn trajectories.
- Future ConversationRecord generation and full-conversation outcome assessment
    require reusable session hosts.

Current limitation:

- The runner now supports multi-turn session reuse, but unified
    conversation-level evidence packing across turns is not yet implemented.

## Optional ADK model configuration

The ADK root agent and its sub-agents share a text-only V0 `BaseLlm` adapter.
Configure both variables before selecting ADK mode:

- `MODEL_PROVIDER`: set to `openai`; there is no provider fallback.
- `MODEL_NAME`: the model identifier supported by the selected provider.
- `OPENAI_API_KEY` must be set in the process environment.

The optional integrations do not affect deterministic scenario generation.
The adapter currently supports text requests and one final text response only;
streaming, tools, structured output, multimodal content, non-default generation
settings, and usage metadata are unsupported. Tests cover the existing ADK
agent tree with mocked clients. No live OpenAI smoke test is implied.

## Verification Operating Modes

1. Online behaviour verification (turn-level)
- verify_turn_behaviour(...) consumes one ExecutionTrace.
- Produces business signals and behaviour/governance/operational evidence.
- Produces behaviour assessment for the current turn.
- Does not emit a final journey-aware outcome verdict per isolated turn.

2. Offline conversation verification (conversation-level)
- verify_completed_conversation(...) runs after conversation completion.
- Aggregates behaviour evidence across collected turn traces.
- Computes journey-aware outcome evidence from conversation-level stages and scores.
- Produces one unified conversation-level final assessment.

Important boundary:

- Journey-aware weighting is conversation-level and should not be interpreted as
    a final single-turn outcome verdict.

## Verification And Journey Status

Implemented now:

- Unified verification pipeline for behaviour + outcome evidence assessment.
- Journey taxonomy, deterministic classifier, and weighted scorer.
- Fifteen deterministic scenarios covering nominal execution, policy controls,
    routing/loop behaviour, recovery, escalation, and journey-aware outcomes.
- Notebooks for reproducible comparisons.

Not yet wired as a single online runtime verdict flow:

- Full conversation-level evidence pack that fuses all turns in one runtime
    artifact.

## Paper Reference

Verifying Enterprise Conversational Agents: Trace Signals and Journey-Aware
Scoring (NeurIPS 2026 Workshop on Reliable and Trustworthy AI Systems)
