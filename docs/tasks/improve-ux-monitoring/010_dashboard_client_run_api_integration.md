# Task 010: Add Dashboard Client Support For Run APIs

Status: Planned

## Objective

Teach the dashboard client layer about the new run-management API endpoints.

## Scope

- add request and response types for browser-started runs
- add API client helpers for start, status, and report fetches
- keep the new functions close to existing session API helpers

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/types/telemetry.ts`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/lib/api.ts`

## Dependencies

- [007_start_research_run_api.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/007_start_research_run_api.md)
- [008_research_run_status_api.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/008_research_run_status_api.md)
- [009_session_report_api.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/009_session_report_api.md)

## Acceptance Criteria

- the dashboard can start a run and poll its status using typed helpers
- new client types are explicit and do not overload the existing session list types
- the client layer keeps backend URL logic centralized

## Suggested Verification

- run `npm run build` in `/Users/jjae/Documents/guthib/cc-deep-research/dashboard`

