# Task 014: Add Active Run Stop Contract And Backend Flow

Status: Done

## Objective

Extend session management beyond deletion by allowing operators to stop browser-started runs cleanly before deciding whether historical artifacts should remain or be removed.

## Scope

- define a stop or cancel contract for in-process dashboard-owned research runs
- add backend route support for stopping a single run by `run_id`
- teach the job registry to cancel individual tasks and report a terminal cancelled or interrupted state
- make the backend preserve clear session status after cancellation instead of leaving abandoned "running" rows behind

## Target Files

- `src/cc_deep_research/research_runs/jobs.py`
- `src/cc_deep_research/research_runs/models.py`
- `src/cc_deep_research/web_server.py`
- `dashboard/src/types/telemetry.ts`

## Dependencies

- [010_deletion_safety_and_validation.md](010_deletion_safety_and_validation.md)

## Acceptance Criteria

- a browser-started run can be stopped without restarting the dashboard backend
- run-status polling exposes cancellation as a distinct terminal outcome
- stopping a run and deleting a session are separate, non-overloaded operations

## Suggested Verification

- run `uv run pytest tests/test_web_server.py tests/test_research_run_service.py`
