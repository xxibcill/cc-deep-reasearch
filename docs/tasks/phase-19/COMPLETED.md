# Phase 19 - Dashboard Reliability & Observability

## Summary

Completed all 5 tasks in phase 19 for improved dashboard reliability and operator diagnostics.

## Completed Tasks

### P19-T1: Dashboard Observability
- Added `request-telemetry.ts`: tracks request IDs, timing, retry counts, and sanitized error classification for all API calls
- Added `useRequestTelemetry.ts` hook: polls recent request failures every 2s for use in debug export
- API calls through `api.ts` now record telemetry entries (no secret/prompt/logging)

### P19-T2: Standard Async State Patterns
- Added `async-state.tsx`: reusable `LoadingState`, `ErrorState` (with route-specific guidance), `PartialErrorState` components
- Updated `benchmark/page.tsx` to use `ErrorState` with retry and route hint
- `session-list.tsx` uses new `SessionListErrorState` with `session_list` route hint

### P19-T3: WebSocket Health Diagnostics
- Extended `LiveStreamStatus` type with `ReconnectHistoryEntry[]` and `lastSuccessAt`
- Updated `websocket.ts` to record reconnect history (attempt, timestamp, close code/reason, wasClean, tookMs) on every close
- Added `appendReconnectHistory` to store (capped at 20 entries)
- Added collapsible `CollapsiblePanel` diagnostic in `session-telemetry-workspace.tsx` showing reconnect table when reconnecting/failed/historical

### P19-T4: Actionable API Errors
- Rewrote `error-messages.ts` with comprehensive error guidance map covering: network, timeout, backend_unavailable, active_session_conflict, missing_artifact, validation_conflict, permission_configuration, provider_failure, websocket
- Added route-specific guidance for: monitor, content_gen_pipeline, content_gen_brief, content_gen_script, settings, benchmark, report, export, session_list
- Route hints (`ErrorRoute` type) enable per-flow guidance

### P19-T5: Dashboard Debug Export
- Added `useDebugExport.ts` hook: builds and downloads a sanitized debug JSON bundle
- Added backend endpoint `GET /api/sessions/{session_id}/debug-export` returning session summary without secrets
- Bundle includes: schema_version, exported_at, session_id, route, session metadata, recent API failures (sanitized), websocket state (phase, close codes, reconnect history), UI state (view_mode, filters), config (API base URL only)
- Added "Export debug" button to `session-telemetry-workspace.tsx` action bar

## Verification

- TypeScript: `npx tsc --noEmit` passes
- Python: `uv run ruff check src/` passes
- Python mypy: passes for session_routes.py
- Dashboard build: `npm run build` completes successfully
- Lint: `npm run lint` passes
- Core tests: 63 orchestration tests pass
