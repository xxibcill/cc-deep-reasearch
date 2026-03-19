# Task 002: Add Derived Trace APIs And Full History Access

Status: Todo

## Objective

Make the backend answer the five operator questions directly so the UI does not need to reconstruct semantics from raw events. This task should expose narrative, state-change, degradation, and failure views, and replace tail-only history with proper paged access.

## Scope

- extend live and historical telemetry query helpers with derived outputs
- add API response fields for narrative and operator-focused summaries
- replace tail-oriented history access with cursor-based pagination by `sequence_number`
- keep WebSocket history and REST history behavior consistent

## Required Derived Outputs

The session detail path should expose at least:

- `narrative`
- `critical_path`
- `state_changes`
- `decisions`
- `degradations`
- `failures`
- `active_phase`
- paged raw `events`

Each derived output should be built in Python, not inferred only in the browser.

## API Work

Update the session detail and history endpoints to support:

- full event pagination by cursor or sequence range
- stable ordering guarantees
- consistent live versus historical behavior
- derived operator summaries in the detail payload

Recommended endpoint changes:

- enrich `GET /api/sessions/{session_id}`
- replace or extend `GET /api/sessions/{session_id}/events`
- extend `/ws/session/{session_id}` history requests to support cursors instead of only `limit`

## Target Files

- `src/cc_deep_research/telemetry/live.py`
- `src/cc_deep_research/telemetry/query.py`
- `src/cc_deep_research/telemetry/tree.py`
- `src/cc_deep_research/web_server.py`
- `src/cc_deep_research/event_router.py`
- `dashboard/src/lib/websocket.ts`
- `dashboard/src/types/telemetry.ts`

## Implementation Notes

- derive narrative from ordered semantic events, not from brittle string matching where possible
- critical path can start simple: longest-duration phase/agent/tool chain visible from emitted timing data
- paged history should not silently truncate old events the way `event_tail` does today
- preserve compatibility for current consumers while introducing richer detail payloads
- if historical DuckDB queries cannot provide a derived view yet, normalize historical rows into the same in-memory event shape and reuse live builders

## Acceptance Criteria

- session detail responses include derived operator-facing fields beyond raw events
- event history can be paged deterministically across large sessions
- WebSocket history requests can fetch older slices without replacing the whole event model incorrectly
- live sessions and historical sessions return the same high-level response shape
- frontend consumers no longer need to infer all phase/state/failure semantics locally

## Suggested Verification

- add API coverage in `tests/test_web_server.py`
- add live-reader and query-helper coverage in `tests/test_telemetry.py`
- add dashboard websocket/client normalization coverage where needed
- manually inspect one active run and one completed historical run through the API

## Dependencies

- `trace_001_trace_contract_hardening.md`

## Out Of Scope

- full compare UI
- replay harness
- benchmark golden traces
