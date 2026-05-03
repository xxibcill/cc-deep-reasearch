# P16-T7: Remove CLI Entry Point

## Summary

Delete the legacy CLI module and remove the console script entry from `pyproject.toml`. This is the final step — only do this after all preceding tasks are complete.

## Details

1. Remove `cc-deep-research = "cc_deep_research.cli.main:main"` from `[project.scripts]` in `pyproject.toml`
2. Delete `src/cc_deep_research/cli/` directory
3. Update `tests/test_knowledge_cli.py` — either delete it or update imports if it tests API routes that still exist
4. Update `tests/test_knowledge_benchmark_gates.py` — remove any `from cc_deep_research.cli.main import knowledge` imports
5. Verify no remaining imports of `cc_deep_research.cli` anywhere in the codebase

## Acceptance Criteria

- `pyproject.toml` has no `cc-deep-research` console script
- `src/cc_deep_research/cli/` directory does not exist
- No Python files import `cc_deep_research.cli`
- All tests pass