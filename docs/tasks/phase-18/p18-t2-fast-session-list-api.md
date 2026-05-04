# P18-T2: Fast Paginated Session List API

## Summary

Make `/api/sessions` use a focused session-summary query instead of loading full dashboard historical datasets and filtering them in Python.

## Details

1. Add a dedicated telemetry query for session summaries that returns only fields required by the dashboard session list.
2. Push `search`, `status`, `archived_only`, `active_only`, `sort_by`, `sort_order`, `limit`, and cursor behavior as close to the data source as practical.
3. Avoid calling `query_dashboard_data()` from the session list route because it also loads global events, agent timeline, and phase-duration datasets that the list does not render.
4. Preserve merging behavior across live telemetry sessions, persisted DuckDB sessions, and `SessionStore` metadata.
5. Keep session-list response shape compatible with `dashboard/src/lib/api.ts`.
6. Add backend tests for pagination, filtering, archive visibility, active session precedence, and saved-session fallback rows.

## Acceptance Criteria

- `/api/sessions` no longer calls `query_dashboard_data()` for the default list path.
- Response payloads include the same public fields currently consumed by the dashboard.
- Pagination remains stable when active and historical sessions are mixed.
- Search and status filters return the same visible results as before.
- Existing session route tests pass, with new coverage for the optimized query path.
