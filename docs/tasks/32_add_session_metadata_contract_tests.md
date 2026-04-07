# Task 32: Add Session Metadata Contract Tests

## Status: Done

## Goal

Pin the metadata contract with focused tests so later refactors cannot drift silently.

## Scope

- add positive tests for quick, standard, and deep runs
- assert stable keys and nested shapes
- assert degraded runs still produce the documented minimum contract

## Primary Files

- `tests/test_orchestrator.py`
- `tests/test_orchestration.py`

## Acceptance Criteria

- tests fail if required metadata keys disappear or change shape
- degraded execution paths are covered

## Validation

- `uv run pytest tests/test_orchestrator.py tests/test_orchestration.py -v`
