# Task 016: Split Telemetry Analytics

Status: Done

## Objective

Separate DuckDB ingestion and analytics queries from live telemetry helpers.

## Scope

- move ingestion into a dedicated analytics module
- group dashboard query helpers by concern
- keep CLI and dashboard callers stable through a compatibility layer

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/telemetry.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/telemetry/ingest.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/telemetry/query.py`

## Dependencies

- [015_split_monitoring_and_live_telemetry.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/015_split_monitoring_and_live_telemetry.md)

## Acceptance Criteria

- telemetry analytics code is no longer mixed with file cache and live-session helpers
- DuckDB-specific logic is isolated
- dashboard and CLI query helpers keep the same output shape

## Suggested Verification

- run `uv run pytest tests/test_telemetry.py tests/test_monitoring.py`
