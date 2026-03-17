# Task 009: Add Session Report API

Status: Complete

## Objective

Expose the final rendered report to the browser through a stable API instead of requiring filesystem knowledge.

## Scope

- add a session- or run-scoped report endpoint
- support the output formats already produced by the shared service
- keep report lookup separate from live event retrieval

## Target Files

- `src/cc_deep_research/web_server.py`
- `src/cc_deep_research/session_store.py`
- `src/cc_deep_research/research_runs/output.py`

## Dependencies

- [003_report_output_materialization.md](003_report_output_materialization.md)
- [008_research_run_status_api.md](008_research_run_status_api.md)

## Acceptance Criteria

- the dashboard can fetch a finished report by session or run identity
- report retrieval does not require the browser to infer on-disk file paths
- the route cleanly distinguishes missing reports from unfinished runs

## Suggested Verification

- run `uv run pytest tests/test_session_store.py tests/test_reporter.py`

