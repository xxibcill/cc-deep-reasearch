# Task 003: Add Workflow Contract Tests

## Objective

Create fixture-based orchestrator tests that lock down workflow behavior before larger retrieval and validation changes land.

## Scope

- add end-to-end tests with mocked providers and mocked content fetching
- cover quick, standard, and deep mode differences
- cover iteration stop conditions
- cover follow-up query deduplication
- cover fallback from parallel to sequential execution
- cover missing provider behavior

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_orchestrator.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_providers.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_monitoring.py`

## Dependencies

- [001_metadata_contract.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/001_metadata_contract.md)
- [002_phase_result_types.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/002_phase_result_types.md)

## Acceptance Criteria

- tests assert behavior, not just happy-path execution
- mocked provider fixtures are reusable for later tasks
- contract regressions fail fast when workflow shape changes

## Suggested Verification

- run `pytest tests/test_orchestrator.py`
