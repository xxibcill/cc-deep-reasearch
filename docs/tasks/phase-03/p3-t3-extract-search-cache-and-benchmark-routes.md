# P3-T3 - Extract Search Cache And Benchmark Routes

## Outcome

Search cache, benchmark, theme, and analytics endpoints are isolated from the app composition file.

## Scope

- Move search cache list/stats/purge/delete/clear routes.
- Move benchmark corpus and run lookup routes.
- Move theme list route.
- Move analytics route and helpers.

## Implementation Notes

- Keep configuration loading behavior equivalent.
- Preserve expensive or file-backed operations behind testable helpers.
- Avoid changing response shapes used by the dashboard.

## Acceptance Criteria

- `web_server.py` no longer owns these route bodies.
- Existing API tests for these domains pass.
- Dashboard pages using these endpoints still work.

## Verification

- Run targeted backend tests for search cache, benchmark, theme, and analytics.
