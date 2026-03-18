# Task 002: Define The Session Delete Contract

Status: Done

## Objective

Introduce a small typed contract for session deletion so the backend, tests, and dashboard client agree on inputs and outputs before implementation.

## Scope

- define request semantics for hard delete, including optional force behavior
- define a response payload that reports what was removed and what was missing
- define failure cases such as active-session conflict and unknown session id
- keep the contract small enough to support a single-session delete first

## Target Files

- `src/cc_deep_research/research_runs/models.py`
- `src/cc_deep_research/web_server.py`
- `dashboard/src/types/telemetry.ts`

## Dependencies

- [001_session_history_inventory.md](001_session_history_inventory.md)

## Acceptance Criteria

- a single response shape exists for successful delete operations
- conflict, not-found, and validation cases are unambiguous
- frontend code does not need to infer delete outcomes from status codes alone

## Suggested Verification

- add or update focused tests for response serialization and status code mapping
