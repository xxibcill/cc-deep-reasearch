# P17-T3: Extract Brief Run Reference Service

## Summary

Extract managed-brief and run-reference compatibility logic from the legacy orchestrator into a small service that can be tested and reused without importing the deprecated orchestrator.

## Details

1. Create a focused service module, for example `src/cc_deep_research/content_gen/brief_run_reference_service.py`.
2. Move or delegate these responsibilities:
   - `establish_brief_reference`
   - `_build_brief_snapshot`
   - `get_brief_for_run`
   - `_load_brief_revision_content`
   - `get_brief_revisions_info`
   - `create_seeded_run_reference`
   - `create_clone_reference`
3. Keep `ContentGenOrchestrator` methods as thin wrappers for compatibility.
4. Add focused tests for inline fallback, missing managed brief fallback, revision pinning, seeded run references, and clone references.
5. Avoid broad imports from `legacy_orchestrator.py` in the new service.

## Acceptance Criteria

- `tests/test_content_gen_briefs.py` passes.
- New service-level tests cover the extracted behavior directly.
- `ContentGenOrchestrator.get_brief_for_run()` remains compatible.
- `legacy_orchestrator.py` no longer contains the managed-brief implementation details.
- `uv run ruff check src/ tests/` and `uv run mypy src/` pass.
