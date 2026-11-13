# Evidence Policy Note

Scope: Current unified verification implementation

## Definitions

### BusinessSignal
A BusinessSignal is a normalized, business-relevant observation extracted from execution trace events (for example safety, routing, execution reliability, or outcome availability).

### VerificationEvidence
VerificationEvidence is an auditable evidence item with:
- evidence_type
- status (pass, warning, fail, indeterminate)
- explanation
- related_signals

The unified system uses VerificationEvidence for both behaviour and journey-aware outcome channels.

## Evidence Types in Current Use

### Behaviour evidence
Represents routing and interaction behaviour quality derived from trace-based signals. A repeated route or sub-agent invocation is classified as behaviour evidence because it describes the execution path, even though the underlying signal type is operational.

### Governance evidence
Represents policy/safety compliance. Governance fail is treated as a hard failure.

### Operational evidence
Represents execution reliability and operational health, including tool or sub-agent failures. Loop-risk signals are promoted to behaviour evidence by the current evidence builder because they describe repeated routing or invocation behaviour.

### Outcome evidence
Outcome evidence currently has two notions:
1. Delivery outcome (trace-derived): did the system deliver a response?
2. Quality outcome (journey-aware): was quality acceptable in business-critical journey stages?

## Indeterminate Evidence Handling

Indeterminate evidence means available artefacts are insufficient for a reliable pass/warning/fail decision in that channel.

For journey-aware verification specifically:
- If journey_stage/quality_score inputs are missing or invalid, indeterminate journey outcome evidence may be recorded for transparency.
- In current runner behavior, indeterminate journey outcome evidence can be excluded from final assessor input so that missing optional journey inputs do not automatically degrade otherwise valid behaviour assessments.

## Outcome FAIL Policy (Post-Update)

After the assessor update, any outcome evidence item with status=fail is treated as a first-class verification failure.

Policy impact:
- Behaviour pass plus outcome fail results in final fail.
- Governance fail still remains a hard fail.
- Execution-reliability warning logic still applies when outcome support is acceptable.

This policy keeps decisions transparent and easy to explain in workshop review.
