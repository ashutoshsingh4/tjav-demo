# Scenario Index: Controlled Assurance-Evidence Demonstrator

The offline demonstrator registers 15 synthetic, deterministic, author-
constructed scenarios. They exercise implemented evidence rules; they are not
an empirical sample or a benchmark of live agents. Journey stages and quality
scores are supplied fixtures.

Authoritative scenario definitions are in
`src/workshop_verify_agents/examples/conversations.py`; trace construction and
expectation checks are in `src/workshop_verify_agents/demo_offline_verification.py`.
The generated results are in
`docs/paper/demo/generated_tables/table_1_baseline_ablation.csv` and the
paper-facing compact tables under `docs/paper/demo/generated_tables/`.

`B`, `J`, and `U` below mean behaviour-only, journey-only, and unified
assessment. `PW` means PASS WITH WARNINGS.

| Scenario | Behaviour (B) | Outcome (J) | Unified (U) | Purpose |
|---|---|---|---|---|
| `mortgage_happy_path` | PASS | PASS | PASS | Nominal path through both evidence lanes. |
| `investment_prompt_injection_handled` | PASS | PASS | PASS | Risk is detected and the configured control is effective. |
| `investment_guaranteed_return_policy_failure` | FAIL | PASS | FAIL | A policy violation fails despite a passing supplied outcome. |
| `mortgage_hidden_eligibility_failure` | PASS | WARNING | PW | A weak eligibility score is moderated by surrounding scores. |
| `investment_suitability_failure` | PASS | FAIL | FAIL | Supplied suitability and recommendation scores fail the outcome lane. |
| `unhandled_prompt_injection` | FAIL | PASS | FAIL | Ineffective control produces a governance failure. |
| `routing_failure` | PW | PASS | PW | Repeated route selection produces behaviour warnings. |
| `tool_failure_recovered` | PW | PASS | PW | A failed tool call is retained as a warning after recovery. |
| `tool_failure_unrecovered` | FAIL | PASS | FAIL | Unrecovered execution failure remains a behaviour-lane failure. |
| `loop_risk` | PW | PASS | PW | Repeated routing/invocation is surfaced as loop risk. |
| `missing_escalation` | FAIL | PASS | FAIL | Required escalation is omitted and governance fails. |
| `critical_stage_hidden_weakness` | PASS | FAIL | FAIL | A weak critical-stage score is hidden by stronger surrounding scores. |
| `recommendation_stage_failure` | PASS | FAIL | FAIL | Poor supplied recommendation-stage quality fails the outcome lane. |
| `outcome_pass_behaviour_fail` | FAIL | PASS | FAIL | Passing outcome evidence cannot erase a policy failure. |
| `outcome_fail_behaviour_pass` | PASS | FAIL | FAIL | Passing behaviour evidence cannot erase a failing outcome. |

The selected main-paper results table contains seven rows. The appendix
scenario-allocation text additionally identifies the controlled exemplars used
to motivate the paper's discussion; its placement labels are editorial, not
experimental findings.

## Reproduce

Generate reports and all four machine-readable table families in an output
directory:

```bash
uv run python -m workshop_verify_agents.assurance_interpretation --output-dir <output-directory>
```

The generator executes all 15 registered scenarios and validates their
declared expectations after deriving evidence and decisions. Expected values
are assertions, not scoring inputs. Some repository-level JSON artifacts and
archived notes reflect earlier scenario iterations; the source registry above
is authoritative.
