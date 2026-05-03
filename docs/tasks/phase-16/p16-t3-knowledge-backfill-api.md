# P16-T3: Add `/api/knowledge/backfill` Endpoint and Dashboard UI

## Summary

Add a dashboard API endpoint and UI for `knowledge backfill` so all saved sessions can be ingested from the browser.

## Details

- Add `POST /api/knowledge/backfill` endpoint in `knowledge_routes.py`
  - Accept optional `limit` (int) and `dry_run` (bool) query params
  - Use `SessionStore()` and `get_default_session_dir()` to enumerate sessions
  - Call `ingest_session()` for each session
  - Return structured JSON with ingested/failed counts and per-session status
- Add backfill trigger UI in the dashboard (e.g., "Run Backfill" button in knowledge page with limit option)
- Show progress and results inline

## Acceptance Criteria

- `POST /api/knowledge/backfill` ingests all sessions and returns results
- Dashboard backfill UI shows ingested/failed counts
- Dry-run mode lists sessions without ingesting