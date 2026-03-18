# Task 005: Extend Saved Session Artifact Deletion

Status: Planned

## Objective

Make saved-session cleanup report structured outcomes instead of only returning a boolean from the session store.

## Scope

- extend session-store deletion behavior so callers can distinguish removed, missing, and failed states
- keep path sanitization and existing storage layout intact
- avoid coupling the session store to telemetry or DuckDB concerns
- preserve backward compatibility for existing CLI usage where practical

## Target Files

- `src/cc_deep_research/session_store.py`
- `src/cc_deep_research/cli/session.py`

## Dependencies

- [003_session_purge_service.md](003_session_purge_service.md)

## Acceptance Criteria

- session-store deletion returns enough information for the purge service to assemble a full result
- current CLI delete behavior still works or is updated intentionally to the new contract
- report artifacts are not silently ignored during delete orchestration

## Suggested Verification

- run `uv run pytest tests/test_session_store.py`
