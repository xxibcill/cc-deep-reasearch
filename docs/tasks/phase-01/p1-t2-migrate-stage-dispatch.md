# P1-T2 - Migrate Stage Dispatch

## Outcome

Stage dispatch is owned by `ContentGenPipeline` and stage orchestrators instead of `legacy_orchestrator.py`.

## Scope

- Move dispatch table ownership out of the legacy file.
- Route `ContentGenPipeline.run_stage()` to the new stage executors.
- Preserve stage order and labels.
- Keep current public imports working during migration.

## Implementation Notes

- Migrate one or two adjacent stages first to validate the pattern.
- Keep the stage interface narrow: context in, context out, dependencies injected or resolved through the pipeline.
- Do not change API payloads in this task.

## Acceptance Criteria

- New dispatch code runs at least one real stage without creating `ContentGenOrchestrator`.
- Stage order remains unchanged.
- Existing stage-specific tests still pass or are replaced with equivalent boundary tests.

## Verification

- Add or run a focused pipeline stage test.
