# Phase 01 - Stabilize Contract And Validation

## Functional Feature Outcome

The opportunity-planning stage reliably produces a valid `OpportunityBrief` with clear operator-visible diagnostics when the brief is weak, malformed, or incomplete.

## Why This Phase Exists

The current opportunity-planning stage is parser-fragile. It depends on exact text headers, fails hard on small contract drift, and only validates that a few fields are present. That is not strong enough if later stages are expected to trust the brief. This phase hardens the contract first so downstream expansion does not rest on brittle assumptions.

## Scope

- Replace or augment the exact-header text contract with a more structured output shape.
- Add semantic validation beyond simple required-field checks.
- Align prompt, parser, and `OpportunityBrief` fields so the stage contract is coherent.
- Surface quality diagnostics in stage traces and operator-facing views.

## Tasks

| Task | Summary |
| --- | --- |
| [P1-T1](./p1-t1-structured-output-contract.md) | Introduce a structured or dual-mode output contract for opportunity planning and migrate parsing safely. |
| [P1-T2](./p1-t2-semantic-validation-and-quality-signals.md) | Add semantic validation rules and operator-visible quality diagnostics for weak briefs. |
| [P1-T3](./p1-t3-model-contract-alignment.md) | Reconcile `OpportunityBrief` fields with what the stage actually produces and stores. |

## Dependencies

- The current prompt and parser behavior in `src/cc_deep_research/content_gen/prompts/opportunity.py` and `src/cc_deep_research/content_gen/agents/opportunity.py` must be understood before refactoring.
- Stage traces and dashboard views must be available for adding diagnostics without breaking existing pipeline observability.

## Exit Criteria

- Small format drift no longer causes avoidable opportunity-stage failures.
- Weak briefs are rejected or flagged with actionable reasons instead of only failing on missing fields.
- `OpportunityBrief`, prompt output, and parser logic are aligned.
- Operators can tell whether a brief is safe to use before backlog generation proceeds.
