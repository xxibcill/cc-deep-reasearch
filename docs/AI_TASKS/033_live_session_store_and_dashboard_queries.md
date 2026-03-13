# Task 033: Add A Live Session Store And Query Layer

Status: Done

## Objective

Support near-real-time browser monitoring by giving the dashboard a query path
for active sessions, event tails, and in-flight subprocess output without
requiring manual re-ingest after the run ends.

## Scope

- add a live session read path on top of persisted telemetry files or a small
  local cache
- support querying:
  - active sessions
  - latest event tail for a session
  - event tree by parent id
  - agent timeline
  - Claude subprocess streams
- keep historical DuckDB analytics working for completed sessions
- minimize duplicate parsing work during dashboard refreshes
- define retention or truncation rules for chunk-heavy subprocess events

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/telemetry.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/dashboard_app.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_telemetry.py`

Potential new files:

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/live_telemetry.py`

## Dependencies

- [030_live_monitor_event_contract.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/030_live_monitor_event_contract.md)
- [032_stream_claude_cli_subprocess_events.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/032_stream_claude_cli_subprocess_events.md)

## Acceptance Criteria

- the dashboard can load an active session that is still writing events
- query helpers can return the latest N events for a session in stable order
- Claude subprocess chunks are available to the UI without waiting for final
  session summary generation
- historical summary queries still work for completed sessions

## Exit Criteria

- an active session can be opened in the browser and refreshed without losing
  ordering or duplicating events
- tests cover active-session reads and chunk-heavy event sequences
- live monitoring does not require a separate external service for v1

## Suggested Verification

- run `uv run pytest tests/test_telemetry.py`
