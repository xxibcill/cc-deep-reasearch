# Task 018: Validate The Monitoring UX End To End

Status: Complete

## Objective

Lock in the new workflow with targeted regression coverage and one explicit end-to-end validation path.

## Scope

- add backend tests for the shared run service and new API routes
- add dashboard smoke coverage where practical, or at minimum build-level regression checks
- perform one manual validation of the full browser-first flow
- capture any residual limitations explicitly in docs or task follow-ups

## Target Files

- `tests/`
- `dashboard/`
- `docs/REALTIME_MONITORING.md`

## Dependencies

- [005_cli_research_command_delegation.md](005_cli_research_command_delegation.md)
- [009_session_report_api.md](009_session_report_api.md)
- [014_session_report_view.md](014_session_report_view.md)
- [017_browser_first_monitoring_docs.md](017_browser_first_monitoring_docs.md)

## Acceptance Criteria

- there is a repeatable validation path for the one-command browser-first workflow
- new backend APIs have regression coverage
- remaining gaps are documented instead of being implicit

## Exit Criteria

- a contributor can run `npm run dev`, open the dashboard, start a query, watch live events, and read the final report
- the CLI still works as a separate local caller of the shared research service

## Suggested Verification

- run targeted `uv run pytest ...` for new backend coverage
- run `npm run build` in `dashboard`
- manually validate one full research run from the browser UI
