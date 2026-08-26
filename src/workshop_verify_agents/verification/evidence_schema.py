"""Pydantic schemas for verification evidence and assessment results.

Evidence objects bridge the signal layer and the final verdict: they group
related ``BusinessSignal`` observations into typed evidence items and roll
them up into a ``VerificationAssessment`` that is suitable for an enterprise
audit log or a compliance dashboard.
"""

from __future__ import annotations

from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class EvidenceType(str, Enum):
    """The aspect of agent behaviour that a piece of evidence covers."""

    behaviour = "behaviour"
    """Whether the agent followed prescribed interaction patterns and routing rules."""

    governance = "governance"
    """Whether applicable regulatory or policy controls were correctly applied."""

    operational = "operational"
    """Whether the agent executed reliably (no crashes, retries, context loss)."""

    outcome = "outcome"
    """Whether the conversation reached the expected resolution."""

    experience = "experience"
    """Whether the agent delivered a high-quality customer experience."""


class EvidenceStatus(str, Enum):
    """Pass/fail status for a single piece of evidence."""

    pass_ = "pass"
    warning = "warning"
    fail = "fail"
    indeterminate = "indeterminate"


class AssessmentStatus(str, Enum):
    """Overall verdict for a full conversation assessment."""

    pass_ = "pass"
    pass_with_warnings = "pass_with_warnings"
    fail = "fail"
    indeterminate = "indeterminate"


class VerificationEvidence(BaseModel):
    """A typed, auditable evidence item derived from one or more BusinessSignals.

    Each item covers one ``EvidenceType`` dimension and aggregates the
    signals relevant to that dimension into a single auditable record.
    """

    evidence_id: str = Field(default_factory=lambda: str(uuid4()))
    """Unique identifier for this evidence item."""

    conversation_id: str
    """Conversation session this evidence belongs to."""

    evidence_type: EvidenceType
    """The aspect of agent behaviour this item covers."""

    related_signals: list[str] = Field(default_factory=list)
    """IDs of the ``BusinessSignal`` objects that contributed to this evidence item."""

    status: EvidenceStatus
    """Whether this evidence dimension passed, warned, failed, or is indeterminate."""

    explanation: str | None = None
    """Narrative explanation of the evidence finding, suitable for an audit record."""

    control_observation: str | None = None
    """Auditable record of any risk detection or control intervention.
    Populated by the policy verifier; None when no policy was triggered.
    Preserved regardless of status so the audit trail remains intact even when PASS."""


class VerificationAssessment(BaseModel):
    """Complete verification result for a single conversation session.

    Produced by ``VerificationAssessor.assess()`` after all signals have been
    extracted and evidence items assembled.  Suitable for storage in an
    enterprise audit log or display in a compliance dashboard.
    """

    conversation_id: str
    """The conversation session being assessed."""

    overall_status: AssessmentStatus
    """The top-level pass/fail verdict for the conversation."""

    evidence_items: list[VerificationEvidence] = Field(default_factory=list)
    """One evidence item per ``EvidenceType`` dimension that was assessed."""

    warnings: list[str] = Field(default_factory=list)
    """Human-readable descriptions of non-critical issues that warrant attention."""

    failures: list[str] = Field(default_factory=list)
    """Human-readable descriptions of critical failures that caused a FAIL verdict."""

    summary: str | None = None
    """Short narrative overview of the assessment outcome."""
