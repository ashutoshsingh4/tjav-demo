"""Reusable journey taxonomy for enterprise conversational verification.

The stage weights in this module represent business criticality, not user
sentiment. A low score in a high-weight stage should move the final
verification rating more than a similar low score in a low-weight stage.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class JourneyStage(str, Enum):
  """Canonical stage names used by classifier, scorer, and notebooks."""

  greeting = "greeting"
  discovery = "discovery"
  clarification = "clarification"
  eligibility_or_suitability = "eligibility_or_suitability"
  recommendation_or_guidance = "recommendation_or_guidance"
  follow_up = "follow_up"
  closing = "closing"


@dataclass(frozen=True)
class JourneyStageDefinition:
  """Definition of one journey stage and its business importance."""

  stage: JourneyStage
  description: str
  default_weight: float
  business_rationale: str


STAGE_REGISTRY: dict[JourneyStage, JourneyStageDefinition] = {
  JourneyStage.greeting: JourneyStageDefinition(
    stage=JourneyStage.greeting,
    description="Opening, rapport, and initial framing of the conversation.",
    default_weight=0.1,
    business_rationale=(
      "Important for usability but rarely where regulated harm occurs."
    ),
  ),
  JourneyStage.discovery: JourneyStageDefinition(
    stage=JourneyStage.discovery,
    description="Collection of customer goals, constraints, and context.",
    default_weight=0.4,
    business_rationale=(
      "Drives downstream quality but usually not a direct regulated action point."
    ),
  ),
  JourneyStage.clarification: JourneyStageDefinition(
    stage=JourneyStage.clarification,
    description="Resolution of ambiguity and confirmation of customer meaning.",
    default_weight=0.5,
    business_rationale=(
      "Misunderstanding here can propagate into unsuitable guidance later."
    ),
  ),
  JourneyStage.eligibility_or_suitability: JourneyStageDefinition(
    stage=JourneyStage.eligibility_or_suitability,
    description=(
      "Checks for affordability, suitability, risk tolerance, or eligibility."
    ),
    default_weight=1.0,
    business_rationale=(
      "Highest risk stage for compliance and customer harm if handled poorly."
    ),
  ),
  JourneyStage.recommendation_or_guidance: JourneyStageDefinition(
    stage=JourneyStage.recommendation_or_guidance,
    description="Delivery of recommendation, guidance, or option framing.",
    default_weight=0.8,
    business_rationale=(
      "Business-critical stage where advice quality and caveats matter most."
    ),
  ),
  JourneyStage.follow_up: JourneyStageDefinition(
    stage=JourneyStage.follow_up,
    description="Post-recommendation checks, next steps, and clarifying follow-up.",
    default_weight=0.4,
    business_rationale=(
      "Important for continuity and risk control, but usually secondary to core checks."
    ),
  ),
  JourneyStage.closing: JourneyStageDefinition(
    stage=JourneyStage.closing,
    description="Conversation closure, recap, and signposting.",
    default_weight=0.1,
    business_rationale=(
      "Low direct compliance risk; primarily UX and completion quality."
    ),
  ),
}


def coerce_stage(stage: JourneyStage | str) -> JourneyStage:
  """Return a JourneyStage from either enum or string value."""
  if isinstance(stage, JourneyStage):
    return stage
  return JourneyStage(stage)


def stage_weight(stage: JourneyStage | str) -> float:
  """Return the default business-importance weight for a journey stage."""
  return STAGE_REGISTRY[coerce_stage(stage)].default_weight


def stage_definition(stage: JourneyStage | str) -> JourneyStageDefinition:
  """Return full stage definition for display, reporting, and notebooks."""
  return STAGE_REGISTRY[coerce_stage(stage)]


def stage_weights() -> dict[str, float]:
  """Return a serialisable map of stage name to default weight."""
  return {stage.value: definition.default_weight for stage, definition in STAGE_REGISTRY.items()}
