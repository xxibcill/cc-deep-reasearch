# Task 007: Add Models Compatibility Layer

Status: Planned

## Objective

Preserve import stability while the model split lands by turning `models` into an explicit compatibility layer.

## Scope

- convert the old `models.py` entrypoint into a compatibility barrel or package initializer
- re-export stable public types intentionally
- avoid re-exporting internal helpers that should become private

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/models.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/models/__init__.py`

## Dependencies

- [003_extract_search_models.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/003_extract_search_models.md)
- [004_extract_analysis_models.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/004_extract_analysis_models.md)
- [005_extract_session_models.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/005_extract_session_models.md)
- [006_extract_llm_and_quality_models.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/006_extract_llm_and_quality_models.md)

## Acceptance Criteria

- existing imports from `cc_deep_research.models` still work
- the compatibility surface is explicit and minimal
- new modules can be adopted incrementally without a flag day

## Suggested Verification

- run `uv run pytest tests/test_models.py tests/test_coordination_imports.py tests/test_orchestrator.py`
