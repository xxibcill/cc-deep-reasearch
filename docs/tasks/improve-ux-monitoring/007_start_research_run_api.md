# Task 007: Add Start Research Run API

Status: Complete

## Objective

Expose an HTTP endpoint that starts a research run from the browser using the shared service.

## Scope

- add `POST /api/research-runs`
- validate request payloads with the shared contract
- start the run as a background async task
- return identifiers needed for the UI to navigate immediately

## Target Files

- `src/cc_deep_research/web_server.py`
- `src/cc_deep_research/research_runs/models.py`
- `src/cc_deep_research/research_runs/jobs.py`

## Dependencies

- [004_research_run_service.md](004_research_run_service.md)
- [006_dashboard_backend_runtime_state.md](006_dashboard_backend_runtime_state.md)

## Acceptance Criteria

- the API can start a research run without any terminal-side caller
- the response includes at least a run id and session id
- the route reuses the shared service instead of reimplementing research execution

## Suggested Verification

- run `uv run pytest tests/test_cli_monitoring.py`

