# Task 34: Add Missing Provider Failure Coverage

## Goal

Harden the system against empty, malformed, or unavailable provider responses.

## Scope

- add tests for provider auth failure
- add tests for timeout and rate-limit behavior
- add tests for empty but valid results
- verify graceful fallback or degradation metadata

## Primary Files

- `tests/test_tavily_provider.py`
- `tests/test_providers.py`
- `tests/test_orchestration.py`

## Acceptance Criteria

- provider failure paths are covered by fixtures
- research runs degrade predictably instead of crashing

## Validation

- `uv run pytest tests/test_tavily_provider.py tests/test_providers.py tests/test_orchestration.py -v`
