# Architecture

```text
Synthetic runtime or OpenAI-backed ADK runtime
                    |
             ExecutionTrace
                    |
             Business signals
                    |
       policy and evidence construction
                    |
          behaviour evidence
                    |
Conversation turns + stages + scores
                    |
        journey-aware outcome evidence
                    |
             unified assessment
```

The `ExecutionTrace` is the shared boundary. Runtime events are normalized before entering the common verification code. Policy verification compares detected risks and observed responses with expected controls. The assessor treats governance or outcome failure as `FAIL`, warnings as `PASS_WITH_WARNINGS`, and all passing evidence as `PASS`.

The live ADK path is optional. The deterministic synthetic path is the supported reviewer reproduction path and does not require external services.
