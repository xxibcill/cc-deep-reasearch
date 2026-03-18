# Task 008: Add Session Delete Action To The Dashboard List

Status: Planned

## Objective

Add a delete control to the session list so operators can manage old history without opening each session first.

## Scope

- add a per-session delete action to the list card UI
- include a confirmation dialog with explicit destructive wording
- disable or hide the action for active sessions if the backend contract requires it
- keep list navigation and delete affordances visually distinct to avoid accidental clicks

## Target Files

- `dashboard/src/components/session-list.tsx`
- `dashboard/src/components/ui/dialog.tsx`

## Dependencies

- [007_dashboard_client_delete_integration.md](007_dashboard_client_delete_integration.md)

## Acceptance Criteria

- a user can delete a session directly from the list view
- the confirmation flow makes clear that telemetry, report, and analytics history are removed
- deleting one session does not break navigation for the rest of the list

## Suggested Verification

- run `npm run lint` in `dashboard`
