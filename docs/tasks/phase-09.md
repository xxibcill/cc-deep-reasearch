# Phase 09 - Content-Gen Lane State Consolidation

## Functional Feature Outcome

Content-gen stages resolve, update, and synchronize lane state through one tested domain path instead of duplicating lane behavior across pipeline, stage, and legacy orchestration code.

## Why This Phase Exists

The content-gen workflow now supports multi-lane execution, but lane helpers are duplicated in the pipeline, stage orchestrators, and legacy orchestrator. That makes lane behavior fragile: a fix to angle resolution, context creation, completion tracking, or primary-lane syncing can easily land in one path and miss another. This phase consolidates the lane state rules first because it is central, in-process, and gives later pipeline refactors a smaller surface to move.

## Scope

- Identify the canonical lane state behaviors currently duplicated across content-gen modules.
- Move lane resolution, context creation, completion recording, and primary-lane synchronization behind one tested implementation.
- Update pipeline, stage, and legacy compatibility paths to use the same behavior.
- Preserve existing content-gen payloads, saved context shape, and dashboard-visible lane output.
- Add focused regression tests for lane selection and synchronization edge cases.

## Tasks

| Task | Summary |
| --- | --- |
| [P9-T1](../tasks/phase-09/p9-t1-consolidate-content-gen-lane-state.md) | Consolidate duplicated content-gen lane state behavior and cover it with focused unit tests. |

## Dependencies

- Existing content-gen pipeline and stage behavior must remain compatible with saved context payloads.
- Legacy orchestrator compatibility should remain intact until the legacy path is retired in a later phase.
- Current multi-lane tests and fixtures should be treated as the behavioral baseline.

## Exit Criteria

- Lane resolution and primary-lane synchronization have one canonical implementation.
- Pipeline, research stage, scripting stage, and legacy compatibility paths produce the same lane state for equivalent inputs.
- Tests cover missing lane IDs, primary lane fallback, completion recording, and context synchronization.
- No dashboard or route payload shape changes are required for lane state consumers.
