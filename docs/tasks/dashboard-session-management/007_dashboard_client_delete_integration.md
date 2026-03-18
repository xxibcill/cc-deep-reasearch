# Task 007: Add Dashboard Client Delete Integration

Status: Planned

## Objective

Teach the dashboard frontend how to call the new delete API and update local state coherently after success or failure.

## Scope

- add a delete-session API helper in the dashboard client
- add delete result and error handling to dashboard state management
- remove deleted sessions from in-memory lists immediately after success
- keep error messages specific for conflict and not-found responses

## Target Files

- `dashboard/src/lib/api.ts`
- `dashboard/src/hooks/useDashboard.ts`
- `dashboard/src/types/telemetry.ts`

## Dependencies

- [006_delete_session_api.md](006_delete_session_api.md)

## Acceptance Criteria

- frontend code can perform a delete without reloading the entire app
- deleted sessions disappear from local state immediately
- API failures surface as actionable UI messages rather than generic errors

## Suggested Verification

- run `npm run lint` in `dashboard`
