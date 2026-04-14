# Task P1-T3: Model Contract Alignment

## Objective

Align `OpportunityBrief` with the fields the opportunity stage actually produces, stores, and expects downstream consumers to use.

## Scope

- Audit current `OpportunityBrief` fields against prompt output and parser behavior.
- Remove orphaned fields from the stage contract or assign them a clear producer.
- Keep docs and shared stage-contract metadata in sync.

## Acceptance Criteria

- No `OpportunityBrief` field is effectively unowned by the stage contract.
- Docs, prompt contract, parser, and model metadata describe the same output shape.
- Tests cover the updated contract shape.

## Advice For The Smaller Coding Agent

- Prefer removing unused ambiguity over preserving speculative fields.
- Update contract registries and tests in the same slice as the model change.
