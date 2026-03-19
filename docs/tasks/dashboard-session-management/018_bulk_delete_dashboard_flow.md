# Task 018: Add Bulk Delete Selection And Review UX

Status: Done

## Objective

Expose bulk delete in the dashboard list with enough review friction that operators can clean history quickly without turning the home page into an unsafe click target.

## Scope

- add multi-select state and per-row selection affordances to the session list
- add a bulk action bar and confirmation dialog that summarizes how many sessions will be removed
- reuse query-state and summary metadata so operators can review the target set before deletion
- clear or retain selection intentionally after partial success instead of leaving stale checked rows behind

## Target Files

- `dashboard/src/components/session-list.tsx`
- `dashboard/src/app/page.tsx`
- `dashboard/src/hooks/useDashboard.ts`
- `dashboard/src/lib/api.ts`

## Dependencies

- [013_dashboard_session_list_filters.md](013_dashboard_session_list_filters.md)
- [017_bulk_delete_service_and_api.md](017_bulk_delete_service_and_api.md)

## Acceptance Criteria

- operators can select multiple historical sessions and delete them in one dashboard flow
- the confirmation UI makes batch scope obvious before any destructive request is sent
- selection, navigation, and card-level actions do not conflict on desktop or mobile layouts

## Suggested Verification

- run `npm run lint` in `dashboard`
- run `npm run build` in `dashboard`
