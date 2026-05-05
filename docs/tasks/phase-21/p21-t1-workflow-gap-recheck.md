# P21-T1: Workflow Gap Recheck

## Summary

Re-check remaining CLI, manual, and undocumented operator workflows against the dashboard and API after the previous dashboard phases.

## Status: COMPLETE

All identified workflow gaps from the P16-T1 CLI audit have been addressed by subsequent phases. This document records the final disposition of each gap.

## P16 CLI Audit Dispositions

### Knowledge Group

| CLI Command | Original Status | Final Disposition |
|---|---|---|
| `knowledge init` | Missing API | Implemented in P16-T2 (`POST /knowledge/vault/init`) |
| `knowledge ingest-session` | Missing API | Implemented in P16-T3 (`POST /knowledge/vault/ingest`) |
| `knowledge backfill` | Missing API | Implemented in P16-T3 (same endpoint, batch-capable) |
| `knowledge rebuild-index` | Missing API | Implemented in P16-T4 (`POST /knowledge/vault/reindex`) |
| `knowledge export-graph` | Missing API | Implemented in P18/P19 via `GET /knowledge/graph` and dashboard UI |
| `knowledge inspect` | Missing API | Implemented via `GET /knowledge/graph` (full graph view) |
| `knowledge lint` | Missing API | Deprecated — no equivalent API; not needed for operator workflows |

### Benchmark Group

| CLI Command | Original Status | Final Disposition |
|---|---|---|
| `benchmark run` | Missing API | Implemented in P16-T5 (`POST /benchmarks/run`) |
| `benchmark compare` | Missing API | Implemented in P16-T6 (`POST /benchmarks/compare`) |

### Session Management (CLI references)

| CLI Command | Original Status | Final Disposition |
|---|---|---|
| Session launch (research run) | Via CLI | Implemented in P17 via `POST /research-runs` and dashboard StartResearchForm |
| Session monitor (live events) | Via CLI | Implemented via `GET /api/sessions/{id}/events` + WebSocket streaming |
| Session delete | Via CLI | Implemented via `DELETE /api/sessions/{id}` and dashboard bulk-delete UI |
| Session archive/restore | Via CLI | Implemented via `POST /api/sessions/{id}/archive` and `restore` |
| Session report | Via CLI | Implemented via `GET /api/sessions/{id}/report` |

## Additional Workflows Verified

### Research Run Lifecycle

- **Launch**: Available via `POST /research-runs` and dashboard StartResearchForm
- **Monitor**: Available via WebSocket endpoint and dashboard monitor page
- **Stop**: Available via `POST /research-runs/{run_id}/stop`
- **Report**: Available via `GET /api/sessions/{session_id}/report`

### Operator Annotations and Triage

- **Add annotation**: Available via `POST /api/sessions/{id}/annotations` (implemented this phase)
- **Update triage status**: Available via `PATCH /api/sessions/{id}/triage` (implemented this phase)
- **Session list triage**: Surfaced in session list badges (implemented this phase)

### Compare Workflows

- **Compare view**: Available via `GET /compare?a={id}&b={id}` — uses existing `getSession` API
- **Baseline suggestions**: Implemented in `compare-utils.ts` `suggestBaselineSessions()`
- **Manual compare**: Available via `/compare` page without pre-selection

### Content Generation Handoff

- **Launch content-gen**: Available via Radar opportunity endpoints (`POST /radar/opportunities/{id}/launch-content-pipeline`) and dashboard UI
- **No manual CLI steps required** for the operator handoff flow

## Intentionally Deprecated / Not Implemented

1. **`knowledge lint`** — No API equivalent. Linting is a local vault concern and does not affect dashboard workflows. Operators who use `knowledge lint` locally may continue to do so; the dashboard has no equivalent.

2. **Raw event tail via CLI** — Removed in P16-T7. The dashboard monitor page provides equivalent real-time event streaming via WebSocket. No operator workflow requires raw event tailing from the CLI.

3. **Direct DuckDB query via CLI** — Deprecated. Dashboard provides structured queries via API endpoints. Raw SQL access is not needed for operator workflows.

## No Remaining Gaps

All operator workflows that were available via CLI before P16 have equivalent or better coverage in the dashboard or API. No active dashboard workflow depends on removed CLI entry points.

## Verification Commands

```bash
# Verify session annotation endpoints
curl -X POST http://localhost:8000/api/sessions/{id}/annotations \
  -H "Content-Type: application/json" \
  -d '{"note": "test"}'

# Verify triage endpoint
curl -X PATCH http://localhost:8000/api/sessions/{id}/triage \
  -H "Content-Type: application/json" \
  -d '{"triage_status": "needs_review"}'

# Verify session list exposes triage_status
curl http://localhost:8000/api/sessions | jq '.[0].triage_status'
```