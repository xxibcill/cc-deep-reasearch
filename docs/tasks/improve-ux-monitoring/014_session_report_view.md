# Task 014: Add Final Report View To The Session Page

Status: Complete

## Objective

Turn the session page into the primary workspace by showing the completed report next to monitoring data.

## Scope

- fetch the final report from the new API
- render the report in a readable panel or tab
- handle loading, empty, and failed states without hiding live monitoring

## Target Files

- `dashboard/src/app/session/[id]/page.tsx`
- `dashboard/src/components/session-details.tsx`
- `dashboard/src/components/session-report.tsx`

## Dependencies

- [009_session_report_api.md](009_session_report_api.md)
- [013_session_run_status_summary.md](013_session_run_status_summary.md)

## Acceptance Criteria

- a completed run exposes its report directly in the browser UI
- report rendering does not replace or break event inspection
- unfinished runs show a clear waiting state instead of a blank panel

## Suggested Verification

- run `npm run build` in `dashboard`

