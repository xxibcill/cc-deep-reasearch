# Task 009: Add Delete Flow To The Session Page

Status: Planned

## Objective

Allow a user who is already inspecting a session to delete it from the session page and recover cleanly afterward.

## Scope

- add a delete action to the session page or session-details header
- use the same confirmation semantics as the list view
- redirect away from the current page after successful delete
- handle the run-id versus session-id distinction cleanly for browser-started runs

## Target Files

- `dashboard/src/app/session/[id]/page.tsx`
- `dashboard/src/components/session-details.tsx`
- `dashboard/src/components/run-status-summary.tsx`

## Dependencies

- [007_dashboard_client_delete_integration.md](007_dashboard_client_delete_integration.md)
- [008_session_list_delete_action.md](008_session_list_delete_action.md)

## Acceptance Criteria

- deleting the currently open session does not leave the user on a broken detail page
- run-backed session pages resolve the correct session id before delete
- the page gives a clear success or redirect outcome instead of a 404 surprise

## Suggested Verification

- run `npm run lint` in `dashboard`
