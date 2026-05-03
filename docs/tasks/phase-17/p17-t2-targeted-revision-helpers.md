# P17-T2: Extract Targeted Revision Helpers

## Summary

Move targeted revision helper logic out of `ContentGenOrchestrator` into a focused module, while preserving the old staticmethod names as deprecated wrappers.

## Details

1. Create `src/cc_deep_research/content_gen/targeted_revision.py`.
2. Move these helpers into module-level functions:
   - `extract_retrieval_gaps`
   - `build_targeted_feedback`
   - `should_use_targeted_mode`
   - `apply_targeted_feedback`
3. Update `ContentGenOrchestrator._extract_retrieval_gaps`, `_build_targeted_feedback`, `_should_use_targeted_mode`, and `_apply_targeted_feedback` to delegate to the new functions.
4. Prefer direct imports from the new module in non-legacy code.
5. Keep behavior byte-for-byte equivalent where tests assert exact feedback text.

## Acceptance Criteria

- `tests/test_iterative_loop.py` passes without changing its public compatibility assertions unless the tests are updated to cover both old and new import paths.
- `ResearchStageOrchestrator` or any future targeted-revision caller can import retrieval-gap helpers without importing `ContentGenOrchestrator`.
- `legacy_orchestrator.py` no longer owns targeted-revision business logic.
- `uv run ruff check src/ tests/` and `uv run mypy src/` pass.
