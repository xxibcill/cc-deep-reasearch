# P17-T1: Compatibility Surface Audit

## Summary

Audit every public or test-used `ContentGenOrchestrator` method before moving code out of `legacy_orchestrator.py`. The output should be a short compatibility map that separates behavior that must remain from legacy internals that can be deleted.

## Details

1. Search for imports and method references to `ContentGenOrchestrator` and `legacy_orchestrator.py`.
2. Classify each referenced method as one of:
   - public compatibility API that must remain as a wrapper
   - test-only helper that should move to a dedicated module
   - legacy internal that can be removed after delegation
3. Confirm normal runtime paths use `ContentGenPipeline`, not `ContentGenOrchestrator`.
4. Add or update a small regression note in the task PR description or docs so future work does not reintroduce direct legacy imports.

## Acceptance Criteria

- A compatibility surface list exists in the implementation PR or a short docs note.
- No new production imports from `cc_deep_research.content_gen.legacy_orchestrator` are introduced.
- The required wrapper methods are identified before extraction starts.
- `uv run ruff check src/ tests/` passes.
