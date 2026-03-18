# Task 006: Add Delete Session API

Status: Done

## Objective

Expose a browser-facing API route that deletes one session and returns a structured result.

## Scope

- add `DELETE /api/sessions/{session_id}`
- support optional force semantics if the shared contract includes them
- map active-session conflicts to `409`
- map unknown sessions to a clear not-found response

## Target Files

- `src/cc_deep_research/web_server.py`
- `src/cc_deep_research/research_runs/jobs.py`

## Dependencies

- [002_session_delete_contract.md](002_session_delete_contract.md)
- [003_session_purge_service.md](003_session_purge_service.md)
- [004_telemetry_and_duckdb_deletion_helpers.md](004_telemetry_and_duckdb_deletion_helpers.md)
- [005_saved_session_artifact_deletion.md](005_saved_session_artifact_deletion.md)

## Acceptance Criteria

- the dashboard can delete a historical session without shell access
- the route does not leave the frontend guessing whether report, telemetry, and analytics layers were removed
- active-session protection is enforced server-side, not only in the UI

## Suggested Verification

- run `uv run pytest tests/test_web_server.py`
