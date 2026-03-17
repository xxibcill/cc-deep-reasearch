# Task 017: Rewrite Monitoring Docs Around The Browser-First Flow

Status: Complete

## Objective

Replace the current multi-terminal monitoring instructions with the new browser-first workflow.

## Scope

- update setup docs to start from `dashboard/npm run dev`
- document the new "start research from the home page" flow
- clarify how the CLI still fits into the system as a separate local entrypoint
- remove or correct stale flags and old three-terminal instructions

## Target Files

- `README.md`
- `docs/REALTIME_MONITORING.md`
- `docs/USAGE.md`
- `dashboard/README.md`

## Dependencies

- [016_dashboard_dev_script_wiring.md](016_dashboard_dev_script_wiring.md)
- [014_session_report_view.md](014_session_report_view.md)

## Acceptance Criteria

- docs describe a one-command startup path with exact ports
- docs describe how to launch research from the browser
- outdated instructions for separate dashboard and research terminals are either removed or clearly marked as legacy

## Suggested Verification

- manually follow the rewritten docs from a clean shell session

