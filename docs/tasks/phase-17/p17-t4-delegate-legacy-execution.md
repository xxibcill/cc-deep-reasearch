# P17-T4: Delegate Legacy Execution

## Summary

Replace deprecated `ContentGenOrchestrator` execution paths with delegation to the canonical `ContentGenPipeline` and `ScriptingRunService`.

## Details

1. Change `ContentGenOrchestrator.run_full_pipeline()` to instantiate and call `ContentGenPipeline`.
2. Preserve the existing method signature, including callbacks, stage range arguments, brief arguments, bypass behavior, and run constraints.
3. Change `run_scripting`, `run_scripting_from_step`, and `run_scripting_iterative` to delegate to `ScriptingRunService`.
4. Keep standalone stage convenience methods either delegated to `ContentGenPipeline` or explicitly marked as compatibility wrappers.
5. Verify that API services and dashboard-triggered pipeline runs still use `ContentGenPipeline` as the normal path.

## Acceptance Criteria

- `ContentGenOrchestrator.run_full_pipeline()` no longer calls `_run_stage` or `_PIPELINE_HANDLERS`.
- Standalone scripting execution does not instantiate legacy pipeline machinery.
- `tests/test_content_gen_pipeline_boundary.py`, `tests/test_content_gen_pipeline_gates.py`, `tests/test_pipeline_run_service.py`, and `tests/test_web_server_content_gen_routes.py` pass.
- `uv run ruff check src/ tests/` and `uv run mypy src/` pass.
