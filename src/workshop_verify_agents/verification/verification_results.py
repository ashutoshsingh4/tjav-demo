"""Lightweight in-memory result models for two-lane verification."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from workshop_verify_agents.verification.evidence_schema import (
    VerificationAssessment,
    VerificationEvidence,
)
from workshop_verify_agents.verification.policy_schema import PolicyVerificationResult
from workshop_verify_agents.verification.signal_schema import BusinessSignal
from workshop_verify_agents.verification.trace_schema import ExecutionTrace


class TurnBehaviourResult(BaseModel):
    """Online turn-level behaviour verification result."""

    conversation_id: str
    turn_index: int
    execution_trace: ExecutionTrace
    business_signals: list[BusinessSignal] = Field(default_factory=list)
    policy_verification_results: list[PolicyVerificationResult] = Field(default_factory=list)
    behaviour_evidence: list[VerificationEvidence] = Field(default_factory=list)
    behaviour_assessment: VerificationAssessment


class ConversationOutcomeResult(BaseModel):
    """Offline conversation-level journey-aware outcome verification result."""

    conversation_id: str
    journey_stage_labels: list[str] = Field(default_factory=list)
    turn_scores: list[float] = Field(default_factory=list)
    journey_aware_result: dict[str, object] = Field(default_factory=dict)
    outcome_evidence: list[VerificationEvidence] = Field(default_factory=list)


class UnifiedConversationResult(BaseModel):
    """Final conversation-level result combining behaviour and outcome lanes."""

    conversation_id: str
    behaviour_results: list[TurnBehaviourResult] = Field(default_factory=list)
    behaviour_evidence_conversation_scope: list[VerificationEvidence] = Field(default_factory=list)
    outcome_result: ConversationOutcomeResult | None = None
    final_assessment: VerificationAssessment
    assessment_mode: Literal["journey_only", "behaviour_only", "unified"] = "unified"
    warnings: list[str] = Field(default_factory=list)
    completeness: Literal[
        "online_behaviour_only",
        "offline_full",
        "offline_missing_outcome",
    ]
