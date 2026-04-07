# Task 35: Define Retry and Timeout Behavior in One Place

**Status: Done**

## Goal

Remove scattered or implicit retry and timeout assumptions from orchestration.

## Scope

- locate current timeout and retry logic for provider calls and parallel researchers
- centralize or document policy clearly
- ensure telemetry records timeout and retry decisions consistently

## Primary Files

- `src/cc_deep_research/orchestration/`
- `src/cc_deep_research/coordination/`
- `src/cc_deep_research/telemetry/`

## Acceptance Criteria

- timeout and retry behavior is owned by a small number of clear functions or config paths
- tests cover timeout and fallback behavior

## Validation

- `uv run pytest tests/test_orchestration.py tests/test_teams.py tests/test_telemetry.py -v`
