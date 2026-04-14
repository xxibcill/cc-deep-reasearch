# Task P1-T2: Semantic Validation And Quality Signals

## Objective

Add validation rules that check whether an opportunity brief is editorially usable, not just whether a few fields are present.

## Scope

- Validate audience specificity.
- Validate problem statements for observability.
- Validate proof requirements for actionability.
- Detect repeated or generic sub-angles.
- Emit quality warnings and a concise summary for operators.

## Acceptance Criteria

- Weak briefs can be flagged even when required fields are technically present.
- Operators can see why a brief is weak from traces or dashboard surfaces.
- Validation behavior is deterministic enough to test.

## Advice For The Smaller Coding Agent

- Start with explicit heuristics before reaching for another model pass.
- Keep warning categories operator-readable and stable.
