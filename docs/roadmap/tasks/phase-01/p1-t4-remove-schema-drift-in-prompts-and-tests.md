# P1-T4 - Remove Schema Drift In Prompts And Tests

## Summary

Fix current references to nonexistent strategy fields and add regression coverage for schema-driven prompt behavior.

## Scope

- Audit prompt builders and agent code for invalid strategy field usage.
- Add or remove prompt references so they match the real schema.
- Add tests covering the upgraded strategy fields used in prompt construction.

## Deliverables

- Clean prompt/agent field usage
- Updated prompt tests
- No known prompt code paths relying on fields absent from `StrategyMemory`

## Dependencies

- P1-T1 field decisions

## Acceptance Criteria

- Prompt code does not access undefined strategy attributes.
- Tests fail if prompt/schema drift is reintroduced.
