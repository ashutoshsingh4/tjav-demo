# Deterministic Scenarios

The offline demo registers five scenarios. They exercise the verification method, not model capability:

| Scenario | Expected outcome | Main point |
|---|---|---|
| `mortgage_happy_path` | PASS | Nominal process and outcome |
| `investment_prompt_injection_handled` | PASS | Detected risk can be controlled effectively |
| `investment_guaranteed_return_policy_failure` | FAIL | Response-level policy violation |
| `mortgage_hidden_eligibility_failure` | PASS_WITH_WARNINGS | Critical-stage weakness hidden by simple averaging |
| `investment_suitability_failure` | FAIL | Journey weighting exposes critical weaknesses |

Run the default example:

```text
uv run python -m workshop_verify_agents.demo_offline_verification
```

Run every scenario:

```text
uv run python -c "from workshop_verify_agents.examples.conversations import list_scenarios; from workshop_verify_agents.demo_offline_verification import demo_offline_verification; [demo_offline_verification(name) for name in list_scenarios()]"
```
