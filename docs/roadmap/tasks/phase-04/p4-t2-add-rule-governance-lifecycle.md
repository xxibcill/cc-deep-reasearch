# P4-T2 - Add Rule Governance Lifecycle

## Summary

Introduce explicit lifecycle controls for reusable rules so they can be promoted, reviewed, expired, and deprecated safely.

## Scope

- Add lifecycle metadata such as status, confidence, evidence count, review date, and deprecation state.
- Implement promotion criteria and retirement criteria enforcement.
- Support operator-visible review decisions for durable rules.

## Deliverables

- Rule lifecycle model and persistence
- Promotion and retirement logic
- Operator-facing review workflow hooks

## Dependencies

- P3-T2 structured learnings
- P3-T3 durable guidance promotion

## Acceptance Criteria

- Reusable rules can be promoted and deprecated with explicit lifecycle state.
- Rule history reflects why a rule changed and when it should be reviewed again.
