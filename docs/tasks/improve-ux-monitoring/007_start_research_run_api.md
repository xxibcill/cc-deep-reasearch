# Task 007: Add Start Research Run API

Status: Planned

## Objective

Expose an HTTP endpoint that starts a research run from the browser using the shared service.

## Scope

- add `POST /api/research-runs`
- validate request payloads with the shared contract
- start the run as a background async task
- return identifiers needed for the UI to navigate immediately

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/web_server.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/research_runs/models.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/research_runs/jobs.py`

## Dependencies

- [004_research_run_service.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/004_research_run_service.md)
- [006_dashboard_backend_runtime_state.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/006_dashboard_backend_runtime_state.md)

## Acceptance Criteria

- the API can start a research run without any terminal-side caller
- the response includes at least a run id and session id
- the route reuses the shared service instead of reimplementing research execution

## Suggested Verification

- run `uv run pytest tests/test_cli_monitoring.py`

