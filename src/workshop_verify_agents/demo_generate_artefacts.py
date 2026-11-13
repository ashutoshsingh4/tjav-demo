"""Generate and persist verification pipeline artefacts for all registered scenarios.

Default layout (overwrite on each run — stable path for paper reference):

    artefacts/{scenario_name}/

Timestamped layout (--timestamped flag — preserves each run as a snapshot):

    artefacts/{YYYYMMDD_HHMMSS}/{scenario_name}/

Each scenario directory contains:

    turn_NN_trace.json       ExecutionTrace for that turn
    turn_NN_signals.json     BusinessSignals extracted from the trace
    turn_NN_evidence.json    VerificationEvidence items (behaviour lane)
    turn_NN_assessment.json  Per-turn VerificationAssessment
    unified_assessment.json  UnifiedConversationResult (both lanes)
    manifest.json            Pipeline summary and file index

Run with:
    uv run python -m workshop_verify_agents.demo_generate_artefacts
    uv run python -m workshop_verify_agents.demo_generate_artefacts --timestamped

These artefacts are intended as supplementary paper evidence. The default
(non-timestamped) run is safe to commit as a reproducible reference output.
They are produced by the deterministic offline path and do not require the
ADK runtime or any external service.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from workshop_verify_agents.artefact_writer import write_scenario_artefacts
from workshop_verify_agents.demo_offline_verification import _build_demo_trace_for_exchange
from workshop_verify_agents.examples.conversations import get_exchanges, get_scenario, list_scenarios
from workshop_verify_agents.verification.offline_verifier import verify_completed_conversation
from workshop_verify_agents.verification.online_verifier import verify_turn_behaviour

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_OUTPUT = _REPO_ROOT / "artefacts"


def _resolve_output_dir(base: Path, timestamped: bool) -> Path:
    """Return the effective output directory for this run."""
    if timestamped:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return base / run_id
    return base


def generate_scenario_artefacts(scenario_name: str, output_dir: Path) -> None:
    """Run one scenario and write all pipeline artefacts to *output_dir*."""
    scenario = get_scenario(scenario_name)
    turns = list(scenario.get("turns", []))
    exchanges = get_exchanges(scenario)
    stages = [str(exchange["journey_stage"]) for exchange in exchanges]
    scores = [float(exchange["quality_score"]) for exchange in exchanges]
    conversation_id = f"artefact::{scenario_name}"

    behaviour_results = []
    for index, exchange in enumerate(exchanges):
        trace = _build_demo_trace_for_exchange(
            conversation_id=conversation_id,
            exchange_index=index,
            user_turn=turns[index * 2],
            agent_turn=turns[index * 2 + 1],
            journey_stage=str(exchange["journey_stage"]),
        )
        behaviour_results.append(
            verify_turn_behaviour(
                conversation_id=conversation_id,
                turn_index=index,
                execution_trace=trace,
            )
        )

    unified = verify_completed_conversation(
        conversation_id=conversation_id,
        behaviour_results=behaviour_results,
        conversation_turns=turns,
        turn_scores=scores,
        journey_stage_labels=stages,
        conversation_exchanges=exchanges,
    )

    written = write_scenario_artefacts(
        scenario_name=scenario_name,
        behaviour_results=behaviour_results,
        unified=unified,
        output_dir=output_dir,
    )

    print(f"  {scenario_name}: {unified.final_assessment.overall_status} "
          f"({len(written)} files -> {output_dir / scenario_name})")


def generate_all_artefacts(output_dir: Path | None = None, timestamped: bool = False) -> None:
    """Generate artefacts for every registered scenario."""
    out = _resolve_output_dir(output_dir or _DEFAULT_OUTPUT, timestamped)
    out.mkdir(parents=True, exist_ok=True)
    print(f"Writing artefacts to: {out}\n")
    for name in list_scenarios():
        generate_scenario_artefacts(name, out)
    print(f"\nDone. {len(list_scenarios())} scenarios written.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate deterministic verification pipeline artefacts."
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        type=Path,
        help="Base directory for artefacts (default: artefacts/ at repo root).",
    )
    parser.add_argument(
        "--scenario",
        default=None,
        help="Run a single named scenario instead of all registered scenarios.",
    )
    parser.add_argument(
        "--timestamped",
        action="store_true",
        help=(
            "Nest output under a YYYYMMDD_HHMMSS subdirectory so each run is "
            "preserved as a snapshot. Without this flag the stable path is "
            "overwritten, which is the recommended mode for paper-reference artefacts."
        ),
    )
    args = parser.parse_args()
    base = args.output_dir or _DEFAULT_OUTPUT
    out = _resolve_output_dir(base, args.timestamped)
    if args.scenario:
        out.mkdir(parents=True, exist_ok=True)
        generate_scenario_artefacts(args.scenario, out)
    else:
        generate_all_artefacts(base, args.timestamped)
