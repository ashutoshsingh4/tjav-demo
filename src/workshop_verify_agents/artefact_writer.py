"""Serialises verification pipeline artefacts to JSON files.

Intended for supplementary paper evidence and offline inspection.

Public API
----------
    write_scenario_artefacts(scenario_name, behaviour_results, unified, output_dir)
        -> dict[str, Path]
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from workshop_verify_agents.verification.verification_results import (
    TurnBehaviourResult,
    UnifiedConversationResult,
)


def write_scenario_artefacts(
    scenario_name: str,
    behaviour_results: list[TurnBehaviourResult],
    unified: UnifiedConversationResult,
    output_dir: Path,
) -> dict[str, Path]:
    """Write all pipeline artefacts for one scenario to *output_dir/scenario_name/*.

    Returns a mapping of artefact label → file path for all files written.
    """
    scenario_dir = output_dir / scenario_name
    scenario_dir.mkdir(parents=True, exist_ok=True)

    written: dict[str, Path] = {}
    turn_count = 0

    for result in behaviour_results:
        i = result.turn_index
        turn_count = max(turn_count, i + 1)

        trace_path = scenario_dir / f"turn_{i:02d}_trace.json"
        trace_path.write_text(
            result.execution_trace.model_dump_json(indent=2),
            encoding="utf-8",
        )
        written[f"turn_{i:02d}_trace"] = trace_path

        signals_path = scenario_dir / f"turn_{i:02d}_signals.json"
        signals_path.write_text(
            _dump_list(result.business_signals),
            encoding="utf-8",
        )
        written[f"turn_{i:02d}_signals"] = signals_path

        evidence_path = scenario_dir / f"turn_{i:02d}_evidence.json"
        evidence_path.write_text(
            _dump_list(result.behaviour_evidence),
            encoding="utf-8",
        )
        written[f"turn_{i:02d}_evidence"] = evidence_path

        assessment_path = scenario_dir / f"turn_{i:02d}_assessment.json"
        assessment_path.write_text(
            result.behaviour_assessment.model_dump_json(indent=2),
            encoding="utf-8",
        )
        written[f"turn_{i:02d}_assessment"] = assessment_path

        if result.policy_verification_results:
            policy_path = scenario_dir / f"turn_{i:02d}_policy_verification.json"
            policy_path.write_text(
                _dump_list(result.policy_verification_results),
                encoding="utf-8",
            )
            written[f"turn_{i:02d}_policy_verification"] = policy_path

    unified_path = scenario_dir / "unified_assessment.json"
    unified_path.write_text(
        unified.model_dump_json(indent=2),
        encoding="utf-8",
    )
    written["unified_assessment"] = unified_path

    manifest_path = scenario_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            _build_manifest(scenario_name, unified, written, turn_count),
            indent=2,
        ),
        encoding="utf-8",
    )
    written["manifest"] = manifest_path

    return written


def _dump_list(items: list[Any]) -> str:
    """Serialise a list of Pydantic models to a JSON array string."""
    return "[\n" + ",\n".join(item.model_dump_json(indent=2) for item in items) + "\n]"


def _build_manifest(
    scenario_name: str,
    unified: UnifiedConversationResult,
    written: dict[str, Path],
    turn_count: int,
) -> dict[str, Any]:
    outcome = unified.outcome_result
    simple = None
    weighted = None
    if outcome and isinstance(outcome.journey_aware_result, dict):
        simple = outcome.journey_aware_result.get("simple_average")
        weighted = outcome.journey_aware_result.get("journey_weighted_score")

    return {
        "scenario_name": scenario_name,
        "conversation_id": unified.conversation_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "turn_count": turn_count,
        "completeness": unified.completeness,
        "final_status": unified.final_assessment.overall_status,
        "pipeline_summary": {
            "policy_verifications_triggered": sum(
                len(result.policy_verification_results)
                for result in unified.behaviour_results
            ),
            "policy_interventions_handled": sum(
                sum(1 for policy in result.policy_verification_results if policy.control_effective)
                for result in unified.behaviour_results
            ),
            "policy_violations_detected": sum(
                sum(1 for policy in result.policy_verification_results if not policy.policy_compliant)
                for result in unified.behaviour_results
            ),
            "behaviour_evidence_categories": [
                e.evidence_type for e in unified.behaviour_evidence_conversation_scope
            ],
            "behaviour_evidence_statuses": [
                e.status for e in unified.behaviour_evidence_conversation_scope
            ],
            "outcome_simple_average": simple,
            "outcome_journey_weighted_score": weighted,
        },
        "files": {label: path.name for label, path in written.items()},
    }
