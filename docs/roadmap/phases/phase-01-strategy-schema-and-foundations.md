# Phase 01 - Strategy Schema And Foundations

## Status

Done. All four tasks completed. `StrategyMemory` now expresses identity, pillars, proof policy, audience universe, platform rules, and CTA policy via structured models. Backward compatibility preserved. API, TypeScript types, and prompts are aligned.

## Functional Feature Outcome

The content system can store and validate a richer strategy object that is expressive enough to constrain content generation and safe enough to support structured dashboard editing.

## Why This Phase Exists

The current strategy layer has two problems: it is under-modeled for the product direction in `docs/improve-strategy-guide.md`, and the parts that already exist are only partially exposed to clients. Before improving the dashboard, the backend model, persistence path, API contract, and prompt expectations need to agree on what strategy is. This phase creates that stable foundation and removes current schema drift.

## Scope

- Expand `StrategyMemory` to include the missing global strategy concepts needed for identity, boundaries, proof policy, platform rules, CTA policy, and audience universe.
- Add structured types for content pillars and other nested strategy objects instead of relying on string arrays everywhere.
- Preserve backward compatibility for existing YAML strategy files and existing shallow update flows.
- Fix model and prompt mismatches so downstream stages stop referencing undefined fields.
- Align Python, API, and dashboard TypeScript contracts around the same strategy shape.

## Tasks

| Task | Summary |
| --- | --- |
| [P1-T1](../tasks/phase-01/p1-t1-expand-strategy-schema.md) | Expand the backend strategy schema with missing outer-layer fields and structured object types. |
| [P1-T2](../tasks/phase-01/p1-t2-add-migration-and-storage-compatibility.md) | Add backward-compatible storage migration and update semantics for richer nested strategy data. |
| [P1-T3](../tasks/phase-01/p1-t3-align-api-and-client-contracts.md) | Align router payloads and dashboard types with the upgraded strategy contract. |
| [P1-T4](../tasks/phase-01/p1-t4-remove-schema-drift-in-prompts-and-tests.md) | Remove prompt/schema drift and add coverage for the upgraded strategy foundation. |

## Dependencies

- Agreement on the target outer-layer concepts from [improve-strategy-guide.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/improve-strategy-guide.md).
- No dashboard rewrite should start until the backend contract for pillars and nested rules is stable enough to type against.

## Exit Criteria

- `StrategyMemory` can represent identity, pillars, proof policy, audience universe, platform rules, CTA policy, and richer learning metadata.
- Existing strategy YAML files still load without manual migration.
- Backend API responses and dashboard types expose the same strategy fields.
- No prompt or orchestrator code references nonexistent strategy fields.
