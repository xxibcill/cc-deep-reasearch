# Task 015: Add Dashboard Stop Actions For Active Sessions

Status: Planned

## Objective

Expose the new stop capability in the dashboard so active-session management is available from the same surfaces that already show run health and session detail.

## Scope

- add a stop action to the run-status summary for browser-started runs
- surface stop affordances and post-stop messaging on session routes that currently only show monitoring state
- disable stop actions while a request is in flight and reconcile the local list after success
- keep stop UI clearly separated from delete UI so destructive scope is never ambiguous

## Target Files

- `dashboard/src/components/run-status-summary.tsx`
- `dashboard/src/app/session/[id]/page.tsx`
- `dashboard/src/hooks/useDashboard.ts`
- `dashboard/src/lib/api.ts`

## Dependencies

- [014_active_run_stop_api.md](014_active_run_stop_api.md)

## Acceptance Criteria

- operators can stop an active browser-started run from the dashboard without a page reload
- the current route transitions to a stable interrupted or cancelled state after stop succeeds
- session list state reflects the new terminal status quickly enough for follow-on actions such as delete or archive

## Suggested Verification

- run `npm run lint` in `dashboard`
- run `npm run build` in `dashboard`
