"""Deterministic journey-stage classifier for conversation turns.

This module intentionally avoids LLM inference and uses transparent keyword
heuristics so that Contribution 2 can be demonstrated with reproducible logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from workshop_verify_agents.journey.journey_taxonomy import JourneyStage


_STAGE_KEYWORDS: dict[JourneyStage, tuple[str, ...]] = {
  JourneyStage.greeting: (
    "hello", "hi", "good morning", "good afternoon", "thanks for your help",
  ),
  JourneyStage.discovery: (
    "i want", "i need", "my goal", "i am looking", "can you explain", "first-time buyer",
    "my situation", "i have", "i am planning",
  ),
  JourneyStage.clarification: (
    "do you mean", "to clarify", "can you clarify", "just to confirm", "for example",
    "what do you mean", "could you explain that", "not sure",
  ),
  JourneyStage.eligibility_or_suitability: (
    "affordability", "eligible", "eligibility", "suitability", "risk tolerance",
    "income", "deposit", "credit", "debt", "monthly outgoings", "budget",
    "employment", "time horizon",
  ),
  JourneyStage.recommendation_or_guidance: (
    "recommend", "you should", "best option", "consider", "guidance", "suggest",
    "a sensible approach", "based on this", "next option",
  ),
  JourneyStage.follow_up: (
    "next step", "what should i do next", "anything else", "follow up", "documents",
    "timeline", "after this", "who should i speak to",
  ),
  JourneyStage.closing: (
    "thank you", "that helps", "goodbye", "bye", "anything else i can help",
    "have a good day", "glad to help",
  ),
}

_DEFAULT_STAGE_PROGRESS = {
  JourneyStage.greeting: JourneyStage.discovery,
  JourneyStage.discovery: JourneyStage.clarification,
  JourneyStage.clarification: JourneyStage.eligibility_or_suitability,
  JourneyStage.eligibility_or_suitability: JourneyStage.recommendation_or_guidance,
  JourneyStage.recommendation_or_guidance: JourneyStage.follow_up,
  JourneyStage.follow_up: JourneyStage.closing,
  JourneyStage.closing: JourneyStage.closing,
}


@dataclass(frozen=True)
class JourneyClassification:
  """Classification result for one conversation turn."""

  turn_index: int
  role: str
  text: str
  stage: JourneyStage
  confidence: float
  rationale: str


def classify_turn(
  turn: dict[str, str],
  turn_index: int,
  previous_stage: JourneyStage | None = None,
) -> JourneyClassification:
  """Classify one turn using deterministic keyword and continuity heuristics."""
  role = (turn.get("role") or "unknown").strip().lower()
  text = (turn.get("text") or "").strip()
  lower_text = text.lower()

  scores: dict[JourneyStage, int] = {}
  for stage, keywords in _STAGE_KEYWORDS.items():
    scores[stage] = sum(1 for keyword in keywords if keyword in lower_text)

  # Role priors help disambiguate common enterprise dialog patterns.
  if role == "user":
    scores[JourneyStage.discovery] += 1
  elif role == "agent":
    scores[JourneyStage.recommendation_or_guidance] += 1

  best_stage = max(scores, key=lambda stage: scores[stage])
  best_score = scores[best_stage]
  sorted_scores = sorted(scores.values(), reverse=True)
  second_score = sorted_scores[1] if len(sorted_scores) > 1 else 0

  if best_score <= 1 and previous_stage is not None:
    stage = _DEFAULT_STAGE_PROGRESS[previous_stage]
    confidence = 0.45
    rationale = (
      f"Low lexical evidence (max score={best_score}); "
      f"used continuity transition from {previous_stage.value} to {stage.value}."
    )
  elif best_score == 0:
    stage = JourneyStage.greeting if previous_stage is None else _DEFAULT_STAGE_PROGRESS[previous_stage]
    confidence = 0.35
    rationale = "No stage keywords matched; used deterministic fallback progression."
  else:
    stage = best_stage
    margin = max(best_score - second_score, 0)
    confidence = min(0.55 + (0.10 * best_score) + (0.05 * margin), 0.98)
    rationale = (
      f"Matched stage keywords for {stage.value} (score={best_score}, margin={margin})."
    )

  return JourneyClassification(
    turn_index=turn_index,
    role=role,
    text=text,
    stage=stage,
    confidence=round(confidence, 2),
    rationale=rationale,
  )


def classify_conversation(turns: list[dict[str, str]]) -> list[JourneyClassification]:
  """Classify all turns and return an ordered per-turn journey annotation."""
  classifications: list[JourneyClassification] = []
  previous_stage: JourneyStage | None = None

  for index, turn in enumerate(turns):
    classification = classify_turn(
      turn=turn,
      turn_index=index,
      previous_stage=previous_stage,
    )
    classifications.append(classification)
    previous_stage = classification.stage

  return classifications


def classify_conversation_to_dicts(turns: list[dict[str, str]]) -> list[dict[str, Any]]:
  """Notebook-friendly representation of per-turn classifications."""
  return [
    {
      "turn_index": item.turn_index,
      "role": item.role,
      "text": item.text,
      "stage": item.stage.value,
      "confidence": item.confidence,
      "rationale": item.rationale,
    }
    for item in classify_conversation(turns)
  ]
