# Task 003: Add A Shared Session Purge Service

Status: Planned

## Objective

Move destructive session cleanup into reusable application code instead of embedding filesystem and database mutations in FastAPI route handlers.

## Scope

- introduce a backend service that owns session deletion orchestration
- have the service coordinate saved-session deletion, telemetry deletion, and DuckDB cleanup
- make the service idempotent enough to report partial cleanup clearly
- return structured deletion results instead of bare booleans

## Target Files

- `src/cc_deep_research/web_server.py`
- `src/cc_deep_research/session_store.py`
- `src/cc_deep_research/telemetry/ingest.py`
- `src/cc_deep_research/research_runs/`

## Dependencies

- [002_session_delete_contract.md](002_session_delete_contract.md)

## Acceptance Criteria

- route handlers can call one service method for delete behavior
- the service contains the branching logic for partial or missing artifacts
- follow-on callers such as CLI commands could reuse the same deletion path

## Suggested Verification

- add service-level tests that cover full, partial, and missing-artifact cases
