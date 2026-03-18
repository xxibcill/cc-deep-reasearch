# Task 009: Add Failure-Path Regression Coverage

Status: Done

## Objective

Make sure common expensive failure modes degrade predictably instead of crashing late in a run after collection or analysis work is already done.

## Scope

- add regression tests for malformed LLM JSON, partial deep-analysis payloads, empty findings, and incompatible report inputs
- add regression tests for provider unavailability, partial provider results, and fallback transitions
- verify session metadata records degradation explicitly when the workflow recovers
- prefer specific failure fixtures over broad generic exception mocks

## Target Files

- `tests/test_llm_analysis_client.py`
- `tests/test_orchestrator.py`
- `tests/test_reporter.py`
- `tests/test_validator.py`

## Dependencies

- [003_llm_analysis_schema_contract_tests.md](003_llm_analysis_schema_contract_tests.md)
- [006_analysis_and_reporting_fixture_smoke.md](006_analysis_and_reporting_fixture_smoke.md)
- [007_orchestrator_fixture_end_to_end.md](007_orchestrator_fixture_end_to_end.md)

## Acceptance Criteria

- at least the top known runtime failure modes have explicit regression coverage
- failure recovery paths are asserted via user-visible outputs or session metadata, not only by absence of exceptions
- a contributor can see which failures are expected to fallback and which are expected to fail fast

## Suggested Verification

- run targeted `uv run pytest` coverage for the new failure-path tests

