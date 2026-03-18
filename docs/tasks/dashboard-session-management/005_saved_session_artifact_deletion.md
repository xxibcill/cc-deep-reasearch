# Task 005: Extend Saved Session Artifact Deletion

Status: Done

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

## Implementation

### SessionDeletionResult

Added a `SessionDeletionResult` dataclass to `session_store.py` with the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `deleted` | bool | True if the session file was successfully deleted |
| `missing` | bool | True if the session file did not exist |
| `error` | str \| None | Error message if deletion failed |

The class includes:
- `__bool__()` method for backward compatibility with `if store.delete_session():`
- `success` property that returns True if deletion was successful or file was already missing

### Updated delete_session Method

Changed return type from `bool` to `SessionDeletionResult`:
- Returns `SessionDeletionResult(deleted=True)` on successful deletion
- Returns `SessionDeletionResult(missing=True)` when file doesn't exist
- Returns `SessionDeletionResult(error=str(e))` on OSError

### Updated CLI

The CLI now uses the structured result for better error messages:
- "Session deleted." on successful deletion
- "Error: Session not found." when file is missing (even with race condition)
- "Error: Failed to delete: {error}" when deletion fails

## Acceptance Criteria

- [x] session-store deletion returns enough information for the purge service to assemble a full result
- [x] current CLI delete behavior still works or is updated intentionally to the new contract
- [x] report artifacts are not silently ignored during delete orchestration

## Suggested Verification

- run `uv run pytest tests/test_session_store.py`
