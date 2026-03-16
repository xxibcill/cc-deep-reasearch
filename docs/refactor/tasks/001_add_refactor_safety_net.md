# Task 001: Add Refactor Safety Net

Status: Done

## Objective

Add a small, stable test layer that protects the current CLI, orchestration, session, and telemetry behavior before code is moved across modules.

## Scope

- identify the minimum regression suite for refactor work
- add focused tests for CLI command wiring, orchestrator phase order, session persistence, and telemetry event shape
- avoid broad fixture churn or product-behavior changes

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_orchestrator.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_cli_monitoring.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_session_store.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_telemetry.py`

## Dependencies

None.

## Acceptance Criteria

- refactor-critical behavior is covered by a compact regression suite
- tests assert contracts, not internal implementation details
- later module moves can be validated without running the full suite first

## Suggested Verification

- run `uv run pytest tests/test_orchestrator.py tests/test_cli_monitoring.py tests/test_session_store.py tests/test_telemetry.py`
