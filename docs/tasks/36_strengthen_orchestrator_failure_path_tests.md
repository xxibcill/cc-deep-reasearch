# Task 36: Strengthen Orchestrator Failure-Path Tests

Status: Done

## Goal

Cover the boring but necessary orchestration failures that usually break release quality.

## Scope

- add tests for sequential fallback when parallel collection fails
- add tests for partial analysis results
- add tests for validation follow-up loops stopping correctly
- add tests for missing provider configuration

## Primary Files

- `tests/test_orchestrator.py`
- `tests/test_orchestration.py`
- `tests/test_research_run_service.py`

## Acceptance Criteria

- critical fallback paths are covered
- stop conditions are deterministic under test

## Validation

- `uv run pytest tests/test_orchestrator.py tests/test_orchestration.py tests/test_research_run_service.py -v`
