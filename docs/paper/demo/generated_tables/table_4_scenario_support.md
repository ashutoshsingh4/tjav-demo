## Table 4 Scenario Support

| scenario | intended_phenomenon | explicit_runtime_support | distinct_evidence_path | structured_expectations_validated | suitable_for |
| --- | --- | --- | --- | --- | --- |
| mortgage_happy_path | Provide a nominal mortgage guidance path. | true | false | true | main-paper exemplar |
| investment_prompt_injection_handled | Verify effective handling of prompt injection. | true | true | true | main-paper exemplar |
| investment_guaranteed_return_policy_failure | Verify a guaranteed-return policy violation is failed. | true | true | true | appendix/artefact-only |
| mortgage_hidden_eligibility_failure | Expose a weak eligibility stage hidden by surrounding scores. | true | true | true | appendix/artefact-only |
| investment_suitability_failure | Expose suitability and recommendation weaknesses. | true | true | true | appendix/artefact-only |
| unhandled_prompt_injection | Verify that an unsafe prompt-injection response produces governance failure. | true | true | true | appendix/artefact-only |
| routing_failure | Exercise repeated route selection as a deterministic routing failure. | true | true | true | appendix/artefact-only |
| tool_failure_recovered | Verify that a failed tool call followed by a response is retained as an operational warning. | true | true | true | main-paper exemplar |
| tool_failure_unrecovered | Verify that an unrecovered tool failure remains visible alongside the supplied outcome score. | true | true | true | main-paper exemplar |
| loop_risk | Verify that repeated routing and invocation events are surfaced as loop risk. | true | true | true | appendix/artefact-only |
| missing_escalation | Record a required escalation that is absent from the deterministic response path. | true | true | true | main-paper exemplar |
| critical_stage_hidden_weakness | Show a weak critical-stage score hidden by strong surrounding exchanges. | true | true | true | main-paper exemplar |
| recommendation_stage_failure | Exercise a failing recommendation-stage outcome with nominal execution evidence. | true | true | true | appendix/artefact-only |
| outcome_pass_behaviour_fail | Show that an acceptable outcome score cannot erase an unhandled policy failure. | true | true | true | main-paper exemplar |
| outcome_fail_behaviour_pass | Show that a failing journey outcome is retained despite nominal behaviour evidence. | true | true | true | main-paper exemplar |
