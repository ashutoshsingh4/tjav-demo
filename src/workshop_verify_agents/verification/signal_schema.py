"""Pydantic schemas for business-level verification signals.

A ``BusinessSignal`` represents a single meaningful observation about agent
behaviour, derived from one or more ``TraceEvent`` objects.  Signals are the
currency of the verification pipeline: they abstract away framework-specific
trace details and speak the language of business and compliance requirements.
"""

from __future__ import annotations

from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class SignalType(str, Enum):
    """Broad category of what a signal measures."""

    routing = "routing"
    """How the orchestrator directed the conversation (e.g. which sub-agent was chosen)."""

    safety = "safety"
    """Safety-layer interventions such as blocks, redactions, or policy flags."""

    governance = "governance"
    """Regulatory and compliance checks — affordability, suitability, KYC, etc."""

    execution = "execution"
    """Tool calls, sub-agent handoffs, and internal execution-quality signals."""

    journey = "journey"
    """Journey-stage transitions, stage-boundary violations, or unexpected detours."""

    operational = "operational"
    """Latency, error rates, retry counts, and other operational health indicators."""

    experience = "experience"
    """Customer-experience quality: tone, clarity, response length, empathy."""

    outcome = "outcome"
    """End-of-conversation outcome signals: resolution, escalation, abandonment."""


class SignalSeverity(str, Enum):
    """Ordered severity levels; used for threshold comparisons and weighting."""

    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

    @property
    def numeric(self) -> int:
        """Return an integer weight for arithmetic comparisons (low=1 … critical=4)."""
        return {"low": 1, "medium": 2, "high": 3, "critical": 4}[self.value]


class BusinessSignal(BaseModel):
    """A single business-level observation derived from agent execution traces."""

    signal_id: str = Field(default_factory=lambda: str(uuid4()))
    """Unique identifier for this signal."""

    conversation_id: str
    """Conversation session this signal belongs to."""

    turn_id: str
    """Turn within the conversation at which this signal was observed."""

    signal_type: SignalType
    """Broad category of the signal (see ``SignalType``)."""

    signal_name: str
    """Short, stable machine-readable name.

    Should match the ``signal_type`` value from the rule that fired, e.g.
    ``'compliance_check_omitted'``, ``'low_grounding'``, ``'safety_block'``.
    """

    value: float | str | bool | None = None
    """The measured value, if applicable (e.g. a score, a flag, a label)."""

    severity: SignalSeverity
    """Severity before any journey-stage weighting is applied."""

    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    """Confidence that this signal is a true observation (0.0–1.0)."""

    explanation: str | None = None
    """Human-readable explanation of what was observed and why it matters."""

    source_event_ids: list[str] = Field(default_factory=list)
    """IDs of the ``TraceEvent`` objects from which this signal was derived."""


class SignalBatch(BaseModel):
    """Collection of BusinessSignals produced from a single ExecutionTrace."""

    conversation_id: str
    signals: list[BusinessSignal] = Field(default_factory=list)

    def by_type(self, signal_type: SignalType) -> list[BusinessSignal]:
        """Return all signals of the given type."""
        return [s for s in self.signals if s.signal_type == signal_type]

    def by_severity(self, severity: SignalSeverity) -> list[BusinessSignal]:
        """Return all signals at the given severity level."""
        return [s for s in self.signals if s.severity == severity]

    def has_critical(self) -> bool:
        """Return True if any signal carries critical severity."""
        return any(s.severity == SignalSeverity.critical for s in self.signals)
