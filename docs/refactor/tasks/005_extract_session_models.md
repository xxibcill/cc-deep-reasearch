# Task 005: Extract Session Models

Status: Done

## Objective

Separate session and metadata contract models from search and analysis concerns.

## Scope

- extract session metadata models and `ResearchSession`
- keep `normalize_session_metadata()` behavior stable
- ensure persistence and export code continue to use the same serialized shape

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/models.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/models/session.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/session_store.py`

## Dependencies

- [001_add_refactor_safety_net.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/001_add_refactor_safety_net.md)
- [003_extract_search_models.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/003_extract_search_models.md)
- [004_extract_analysis_models.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/004_extract_analysis_models.md)

## Acceptance Criteria

- session persistence types live in a dedicated module
- session serialization and deserialization stay backward compatible
- downstream callers stop importing unrelated models just to access session contracts

## Suggested Verification

- run `uv run pytest tests/test_models.py tests/test_session_store.py tests/test_benchmark.py`
