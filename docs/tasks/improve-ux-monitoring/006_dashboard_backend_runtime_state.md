# Task 006: Add Dashboard Backend Runtime State

Status: Complete

## Objective

Give the FastAPI app a server-owned runtime container for active research jobs and shared realtime infrastructure.

## Scope

- add app state for the shared `EventRouter`
- add a job registry for active and completed browser-started runs
- keep runtime state local-process only for this task

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/research_runs/jobs.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/web_server.py`

## Dependencies

- [004_research_run_service.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/004_research_run_service.md)

## Acceptance Criteria

- the backend owns one shared event router for all browser-started runs
- there is a dedicated server-side store for run status and task handles
- the implementation is isolated from route handlers behind small helpers or types

## Suggested Verification

- run `uv run pytest tests/test_monitoring.py tests/test_orchestrator.py`
