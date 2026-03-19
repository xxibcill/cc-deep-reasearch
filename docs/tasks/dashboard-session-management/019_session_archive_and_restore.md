# Task 019: Add Archive And Restore Session Lifecycle

Status: Done

## Objective

Introduce a reversible archive state so operators can hide stale history from the default dashboard without permanently deleting session artifacts.

## Scope

- define archive semantics for saved sessions and their dashboard-visible metadata
- add archive and restore routes for historical sessions
- exclude archived items from the default session list while still allowing explicit archived views
- preserve session identity and report access so restore does not require rebuilding artifacts

## Target Files

- `src/cc_deep_research/session_store.py`
- `src/cc_deep_research/research_runs/models.py`
- `src/cc_deep_research/web_server.py`
- `dashboard/src/lib/api.ts`
- `dashboard/src/types/telemetry.ts`
- `dashboard/src/components/session-list.tsx`

## Dependencies

- [011_session_summary_enrichment.md](011_session_summary_enrichment.md)
- [013_dashboard_session_list_filters.md](013_dashboard_session_list_filters.md)

## Acceptance Criteria

- operators can archive a historical session without deleting telemetry, report, or saved-session content
- archived sessions are hidden from the default home-page list but can be restored explicitly
- restore brings a session back without changing its session id or breaking existing links

## Suggested Verification

- run `uv run pytest tests/test_session_store.py tests/test_web_server.py`
- run `npm run lint` in `dashboard`
