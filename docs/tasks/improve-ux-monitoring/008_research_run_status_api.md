# Task 008: Add Research Run Status API

Status: Planned

## Objective

Expose a status endpoint so the dashboard can poll job state without relying only on event streams.

## Scope

- add `GET /api/research-runs/{run_id}`
- report queued, running, completed, and failed states
- include final artifact references and any user-safe error message when available

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/web_server.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/research_runs/jobs.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/research_runs/models.py`

## Dependencies

- [006_dashboard_backend_runtime_state.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/006_dashboard_backend_runtime_state.md)
- [007_start_research_run_api.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/007_start_research_run_api.md)

## Acceptance Criteria

- the dashboard can recover run state after refresh by polling the backend
- failed runs expose a safe, actionable status payload
- completed runs surface enough metadata for report retrieval

## Suggested Verification

- run `uv run pytest tests/test_cli_monitoring.py`

