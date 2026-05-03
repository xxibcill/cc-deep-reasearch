# P17-T5: Remove Legacy Stage Handlers

## Summary

Delete duplicate legacy stage handlers from `legacy_orchestrator.py` after all compatibility wrappers delegate to canonical services.

## Details

1. Remove `_PIPELINE_HANDLERS`.
2. Remove module-level `_stage_*` functions from `legacy_orchestrator.py`.
3. Remove duplicated lifecycle helpers that are already owned by `lifecycle.py`, `pipeline.py`, or `stages/base.py`.
4. Remove imports that only existed for deleted legacy stage handlers.
5. Measure `legacy_orchestrator.py` token size with `o200k_base` after cleanup.
6. Update docs that still describe the legacy orchestrator as containing a full monolithic implementation.

## Acceptance Criteria

- `legacy_orchestrator.py` is below 5k `o200k_base` tokens.
- No `_stage_*` handler functions remain in `legacy_orchestrator.py`.
- No `_PIPELINE_HANDLERS` registry remains.
- `rg "legacy_orchestrator" src tests docs` shows only compatibility imports, docs, or explicit regression references.
- Focused content-gen tests pass, followed by `uv run ruff check src/ tests/` and `uv run mypy src/`.
