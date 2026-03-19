# Task 021: Fix Session Active State Detection

Status: Planned

## Objective

Fix the bug where non-active sessions are incorrectly marked as "active", preventing deletion and causing incorrect UI state.

## Problem Description

Sessions that are not actually running are being incorrectly detected as "active" by the `_is_session_active` function in `session_purge.py`. This causes:
- "Cannot delete: session is currently active" error when trying to delete sessions
- Incorrect UI showing sessions as live when they're not running

## Root Cause Analysis

The issue is in `query_live_sessions` in `telemetry/live.py`. A session is marked as active when:
1. It has no `summary.json` file AND
2. It has no `session.finished` event in events.jsonl

However, this logic incorrectly marks sessions as "active" when:
- They have incomplete/stale telemetry directories
- They were interrupted but don't have proper termination events
- They exist in telemetry but are actually historical sessions

## Scope

- Investigate and fix the active session detection logic in `telemetry/live.py`
- Review `_is_session_active` in `session_purge.py` 
- Ensure archived sessions are properly handled
- Consider using DuckDB historical data to determine if a session is truly active

## Target Files

- `src/cc_deep_research/telemetry/live.py`
- `src/cc_deep_research/research_runs/session_purge.py`
- `src/cc_deep_research/web_server.py`

## Dependencies

- [019_session_archive_and_restore.md](019_session_archive_and_restore.md)
- [020_retention_reconciliation_and_audit.md](020_retention_reconciliation_and_audit.md)

## Acceptance Criteria

- Non-running sessions are not marked as active
- Bulk delete works correctly for historical sessions
- UI correctly shows session status
- Archived sessions can always be deleted

## Suggested Verification

- Run `uv run pytest tests/test_session_store.py tests/test_web_server.py`
- Manually test deleting old sessions via dashboard
- Check that stale telemetry directories don't appear as active
