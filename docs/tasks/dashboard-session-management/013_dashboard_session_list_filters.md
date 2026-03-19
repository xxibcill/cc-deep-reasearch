# Task 013: Add Dashboard Search, Filters, And Pagination Controls

Status: Planned

## Objective

Upgrade the home-page session list from a static recent-items grid into a usable management surface for larger local histories.

## Scope

- add search input, status filter, and active-state controls backed by the queryable session list API
- add load-more or pagination UI so the dashboard can browse past the first page of sessions
- persist list query state in the dashboard store so deletes, stops, and restores do not reset the operator's context
- keep list actions accessible on smaller screens where session cards already compete for space

## Target Files

- `dashboard/src/app/page.tsx`
- `dashboard/src/components/session-list.tsx`
- `dashboard/src/hooks/useDashboard.ts`
- `dashboard/src/lib/api.ts`

## Dependencies

- [012_session_list_query_api.md](012_session_list_query_api.md)

## Acceptance Criteria

- operators can narrow the session list by text and status from the dashboard home page
- loading another page does not drop existing list state or duplicate rows
- list controls remain compatible with later delete, bulk, and archive actions

## Suggested Verification

- run `npm run lint` in `dashboard`
- run `npm run build` in `dashboard`
