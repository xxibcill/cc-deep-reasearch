# Task 012: Add Queryable Session List API

Status: Done

## Objective

Replace the fixed "recent sessions" list contract with a server-side query API that can scale to larger histories and management-oriented filtering.

## Scope

- add query parameters for search text, status filtering, active-only views, sort order, and pagination
- apply filters after live and historical session sources are normalized into one summary model
- keep default behavior backward-compatible for the current home page
- define stable pagination semantics so bulk actions and archive views do not act on shifting rows

## Target Files

- `src/cc_deep_research/web_server.py`
- `src/cc_deep_research/research_runs/models.py`
- `dashboard/src/lib/api.ts`
- `dashboard/src/types/telemetry.ts`

## Dependencies

- [011_session_summary_enrichment.md](011_session_summary_enrichment.md)

## Acceptance Criteria

- operators can query subsets of sessions without fetching the entire merged history
- filtering works consistently for live, interrupted, completed, and archived-ready session states
- pagination and sorting are explicit enough for the frontend to avoid duplicate or skipped rows

## Suggested Verification

- run `uv run pytest tests/test_web_server.py`
