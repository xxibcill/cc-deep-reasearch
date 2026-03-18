# Task 004: Add Telemetry And DuckDB Deletion Helpers

Status: Done

## Objective

Provide explicit helpers for deleting telemetry directories and historical analytics rows by session id.

## Scope

- add a helper to remove `telemetry/<session_id>/`
- add a helper to remove matching rows from `telemetry_events` and `telemetry_sessions`
- keep helper behavior safe when the telemetry directory or DuckDB file does not exist
- make sure DuckDB cleanup does not require a full ingest cycle just to hide one deleted session

## Target Files

- `src/cc_deep_research/telemetry/live.py`
- `src/cc_deep_research/telemetry/ingest.py`
- `src/cc_deep_research/telemetry/__init__.py`

## Dependencies

- [003_session_purge_service.md](003_session_purge_service.md)

## Acceptance Criteria

- one helper removes telemetry files for a session
- one helper removes analytics rows for the same session
- helper behavior is deterministic when artifacts are already absent

## Suggested Verification

- run targeted `uv run pytest` coverage for helper behavior against temporary telemetry and DuckDB fixtures
