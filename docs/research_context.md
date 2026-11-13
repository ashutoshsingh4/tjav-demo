# Research Context

## Research Motivation

Outcome-only evaluation is useful for quick benchmarking but insufficient for enterprise verification. It can hide process failures in safety and routing, and it can miss critical-stage quality failures when scores are averaged over long conversations.

This work treats verification as evidence generation and evidence assessment rather than only endpoint scoring.

## Research Question

Can trace-derived behaviour verification combined with journey-aware outcome verification provide stronger and more auditable evidence than outcome-only evaluation?

## Contribution Rationale

### Contribution 1: Behaviour Verification

Behaviour verification converts execution traces into business-level signals and evidence. The rationale is that reviewers need process-level observability, not only final-response judgments.

Expected value:

- explicit safety and routing evidence
- operational reliability evidence
- transparent rule-based assessment input

### Contribution 2: Journey-Aware Outcome Verification

Journey-aware outcome verification evaluates conversation quality with stage-aware weighting. The rationale is that equal-weight averaging can dilute failures in high-impact stages.

Expected value:

- stronger detection of hidden critical-stage quality issues
- clearer conversation-level interpretation for reviewers

## Evaluation Rationale

Current evaluation assets are 15 author-constructed synthetic and deterministic
scenarios to maximize reproducibility and reviewability of the controlled
demonstrator. They are not a representative sample of live agent behaviour.

Evaluation logic:

- execute the 15 registered deterministic scenarios with supplied journey-stage
  labels and mocked turn-level quality scores
- compare flat mean, minimum turn, critical-stage-only, critical-stage gate,
  and journey-weighted outcomes
- compare behaviour-only, journey-only, and unified assessments
- exercise trace-derived policy, routing, recovery, escalation, operational,
  and response evidence alongside journey-aware outcome evidence

Expected decisions and evidence statuses are checked after derivation; they are
not inputs to the scoring or assessment logic. This validates implementation
consistency within the fixtures, not real-world effectiveness.

Standard operating statement:

Online CLI flow is behaviour-only.
Offline verifier provides conversation-level unified behaviour and outcome assessment.

## Current Limitations

- Journey-aware outcome verification depends on synthetic deterministic scenarios and mocked turn-level scores.
- The scenario suite is controlled and author-constructed; it does not measure
  production-agent performance or generalisation.
- ADK integration is event-driven and normalized through an adapter.
- Journey-stage assignment is rule-based and not learned from production corpora.
- Production-scale annotated evaluation datasets are not yet included.
- The demonstrator does not claim production validation or benchmarking superiority.

## Future Work

- Expand empirical evaluation with non-synthetic datasets.
- Improve structured provenance for outcome evidence.
- Explore tighter runtime integration of journey-stage detection.
- Add broader observability and benchmarking integration.
