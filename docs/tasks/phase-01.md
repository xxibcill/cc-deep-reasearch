# Phase 01 - Content-Gen Pipeline Boundary

## Functional Feature Outcome

Content generation pipeline execution runs through a real pipeline and stage boundary instead of depending on the legacy monolithic orchestrator.

## Why This Phase Exists

The repo already contains `ContentGenPipeline` and per-stage orchestrator files, but `ContentGenPipeline.run_stage()` still delegates back to `ContentGenOrchestrator`, which is exported from `legacy_orchestrator.py`. This means the apparent split is not yet architectural; the legacy monolith remains the actual execution engine.

## Scope

- Move normal stage execution out of `legacy_orchestrator.py`.
- Make `ContentGenPipeline` own stage sequencing, progress callbacks, trace creation, and stage dispatch.
- Preserve compatibility imports through `content_gen/orchestrator.py`.
- Keep LLM and search dependencies behind injectable or mockable boundaries.

## Tasks

| Task | Summary |
| --- | --- |
| [P1-T1](../tasks/phase-01/p1-t1-define-pipeline-execution-contract.md) | Define the public pipeline interface for full runs, single-stage runs, resume, cancellation, and seeded contexts. |
| [P1-T2](../tasks/phase-01/p1-t2-migrate-stage-dispatch.md) | Move stage dispatch from `legacy_orchestrator.py` into `ContentGenPipeline` and stage orchestrators. |
| [P1-T3](../tasks/phase-01/p1-t3-port-stage-gates-and-traces.md) | Move prerequisites, brief gates, stage traces, decision summaries, and phase policy handling into the new pipeline boundary. |
| [P1-T4](../tasks/phase-01/p1-t4-add-pipeline-boundary-tests.md) | Add tests for full run, stage skip/block, cancellation, resume, and seeded backlog item starts. |
| [P1-T5](../tasks/phase-01/p1-t5-deprecate-legacy-orchestrator-path.md) | Keep compatibility imports but stop routing normal execution through `legacy_orchestrator.py`. |

## Dependencies

- Phase 00 baseline must be complete.
- Existing content-gen route behavior must be known before migration.
- LLM-heavy stages need mocked agents or fixtures for deterministic tests.

## Exit Criteria

- `ContentGenPipeline.run_stage()` no longer instantiates `ContentGenOrchestrator`.
- Normal content-gen pipeline execution does not require `legacy_orchestrator.py`.
- Existing content-gen API tests still pass or have documented intentional updates.
- Boundary tests cover pipeline behavior without testing private legacy helpers.
