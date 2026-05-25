# Performance Fix Plan - 2026-05-25

This file translates `docs/review/2026-05-25-performance-review.md` into implementation tasks. Each task is intentionally scoped so it can be handled independently.

## Before Editing

Project instructions require GitNexus impact analysis before editing functions, classes, or methods. If GitNexus MCP tools are available, run impact analysis for the target symbol before changing it. If the index is stale, run:

```bash
npx gitnexus analyze
```

The review session could not access GitNexus MCP tools, and `npx gitnexus status` failed locally. Re-check this before starting code work.

## Task 1: Lightweight Live Events Page

Priority: P1

Primary files:

- `src/cc_deep_research/telemetry/live.py`
- `src/cc_deep_research/web_server_routes/session_routes.py`
- `src/cc_deep_research/web_server_routes/websocket_adapter.py`
- `tests/test_telemetry.py`
- `tests/test_web_server_session_routes.py`

Problem:

`/api/sessions/{session_id}/events` and WebSocket history requests paginate the response but still pay full-session processing costs through `query_live_session_detail()`.

Implementation outline:

1. Add a page-specific live telemetry function, for example `query_live_events_page(session_id, base_dir=None, cursor=None, before_cursor=None, limit=1000)`.
2. For the first implementation, it is acceptable to scan the JSONL file once and collect only the requested page plus total count. Avoid building event trees, subprocess streams, LLM route analytics, and derived summaries.
3. Update `/api/sessions/{session_id}/events` to use this function for live sessions.
4. Update WebSocket `get_history` handling to use this function.
5. Keep the existing full-detail function for `/api/sessions/{session_id}`.

Acceptance criteria:

- `/api/sessions/{session_id}/events` no longer calls `build_event_tree()`, `build_subprocess_streams()`, or `build_llm_route_streams()`.
- WebSocket `get_history` returns the same response shape as today.
- Pagination metadata remains stable: `total`, `has_more`, `next_cursor`, `prev_cursor`.
- Existing telemetry pagination tests still pass.

Suggested tests:

- Add a unit test that monkeypatches expensive builders to raise, then calls the events endpoint.
- Add a slow test with 20,000 live JSONL events and `limit=100`.

## Task 2: Lightweight Session List Summaries

Priority: P1

Primary files:

- `src/cc_deep_research/telemetry/live.py`
- `src/cc_deep_research/web_server_routes/session_routes.py`
- `tests/test_telemetry.py`
- `tests/test_web_server_session_routes.py`

Problem:

`GET /api/sessions` loads full live session snapshots before pagination and may open DuckDB once per session.

Implementation outline:

1. Add a `query_live_session_summaries()` path that avoids full event parsing.
2. Read `summary.json` when present.
3. For active/incomplete sessions, read only minimal event metadata. A practical first pass can read first and last event lines to get timestamps and infer active state.
4. Replace per-session DuckDB checks with one batched lookup for all candidate session IDs.
5. Add bounds or TTL eviction for `_LIVE_SESSION_CACHE`, or split summary cache from full-detail cache.

Acceptance criteria:

- Session list cost is no longer proportional to total event payload size.
- The route still merges live, saved, and historical sessions correctly.
- Active/interrupted/completed classification behavior is preserved.
- Cache memory is bounded or easy to evict.

Suggested tests:

- Generate hundreds of telemetry session directories with large event files and assert list latency under a local budget.
- Monkeypatch DuckDB connect and assert it is not called once per session.

## Task 3: Buffered Telemetry Writes And Bounded Publish

Priority: P1

Primary files:

- `src/cc_deep_research/monitoring.py`
- `src/cc_deep_research/event_router.py`
- `tests/test_monitoring.py`
- `tests/test_telemetry_storage_performance.py`

Problem:

Telemetry emission opens the JSONL file for every event, retains every event in memory, and creates unbounded publish tasks.

Implementation outline:

1. Introduce a small writer abstraction for telemetry JSONL appends. It can keep a file handle open during a session or buffer and flush periodically.
2. Bound `_telemetry_events`, or keep only the summary fields that `finalize_session()` needs for aggregate metadata.
3. Replace unbounded publish tasks with a bounded queue or batched publish per session.
4. Keep failure behavior conservative. Telemetry write failures should not crash research unless existing behavior requires it.

Acceptance criteria:

- `ResearchMonitor.emit_event()` does not open and close the event file for every payload.
- Memory retained by `ResearchMonitor` has a documented bound or reason.
- WebSocket publishing cannot create unlimited pending tasks.
- Existing monitoring tests pass.

Suggested tests:

- Emit 100,000 events with persistence enabled and assert runtime below a documented threshold.
- Simulate slow WebSocket connections and assert the router does not grow unbounded tasks.

## Task 4: Bulk DuckDB Ingestion

Priority: P1

Primary files:

- `src/cc_deep_research/telemetry/ingest.py`
- `tests/test_telemetry_migrations.py`
- `tests/test_telemetry_storage_performance.py`

Problem:

`ingest_telemetry_to_duckdb()` inserts each event row with an individual DuckDB `execute()` call.

Implementation outline:

1. Accumulate event rows per session and insert with `executemany()` or DuckDB appender.
2. Consider staging JSONL import for large files if DuckDB JSON support is available in the supported version.
3. When creating a new database, delay index creation until after data load. Preserve existing database migration behavior.
4. Keep event migration via `migrate_event_record()` intact.

Acceptance criteria:

- Ingestion remains idempotent per session.
- Schema migration tests continue to pass.
- Large dataset ingestion time improves materially from current row-by-row behavior.

Suggested tests:

- Increase the slow perf fixture to at least 100,000 events.
- Compare ingest count and query results against the current implementation.

## Task 5: Indexed Knowledge Graph Access

Priority: P2

Primary files:

- `src/cc_deep_research/knowledge/graph_index.py`
- `src/cc_deep_research/knowledge/retrieval.py`
- `src/cc_deep_research/web_server_routes/knowledge_routes.py`
- `tests/test_knowledge_retrieval_explain.py`
- `tests/test_knowledge_health.py`

Problem:

Retrieval and neighbor expansion scan full graph tables in Python.

Implementation outline:

1. Add `GraphIndex.edges_for_node(node_id)` backed by `idx_edges_source` and `idx_edges_target`.
2. Add `GraphIndex.nodes_by_ids(node_ids)` for batched neighbor loading.
3. Update `/api/knowledge/nodes/{node_id}/neighbors` to use the indexed accessors.
4. Add a retrieval candidate path using SQLite FTS or a normalized token table. Score only candidate nodes.
5. Bound explanation payloads to selected or top-ranked candidates.

Acceptance criteria:

- Neighbor lookup no longer calls `all_edges()`.
- Retrieval results remain compatible with existing tests.
- Query explanations still include selected nodes and score reasons.

Suggested tests:

- Add a graph fixture with many unrelated nodes/edges and assert neighbor lookup stays fast.
- Add retrieval tests for query terms matching labels and properties through the new candidate path.

## Task 6: Move Long-Running API Work To Jobs

Priority: P2

Primary files:

- `src/cc_deep_research/web_server_routes/knowledge_routes.py`
- `src/cc_deep_research/web_server_routes/misc_routes.py`
- `src/cc_deep_research/research_runs/jobs.py`
- `tests/test_web_server_misc_routes.py`
- `tests/test_web_server_session_routes.py`

Problem:

Knowledge backfill, index rebuild, and benchmark run endpoints perform long blocking work inside request handlers.

Implementation outline:

1. Reuse or extend the existing job registry pattern.
2. Return `202 Accepted` with a job ID for backfill, rebuild, and benchmark run.
3. Add status endpoints or reuse existing job status routes.
4. Emit progress events where useful.

Acceptance criteria:

- Long operations do not block the event loop until completion.
- Operators can inspect progress and final errors.
- Existing route behavior has a compatibility path or documented API change.

Suggested tests:

- Use a fake slow operation and assert the initial response is fast.
- Poll job status until completion in a route test.

## Task 7: Dashboard Incremental Derivation

Priority: P2

Primary files:

- `dashboard/src/hooks/useDashboard.ts`
- `dashboard/src/lib/websocket.ts`
- `dashboard/src/components/session-details.tsx`
- `dashboard/src/lib/telemetry-transformers.ts`
- `dashboard/src/hooks/useDashboard.test.ts`

Problem:

The dashboard repeatedly sorts and derives full telemetry structures on each buffered live update and filter change.

Implementation outline:

1. Avoid sorting when appended events are already monotonic by sequence number.
2. Maintain incremental event indexes and category counts in Zustand.
3. Defer graph/timeline derivation until the active view requires it.
4. Consider moving graph/timeline derivation to a Web Worker for large sessions.
5. Reduce initial WebSocket history from 1,000 events if product behavior allows it.

Acceptance criteria:

- Appending a live batch does not always rebuild every derived structure.
- UI behavior stays the same for graph, table, detail, and filters.
- Large-session guardrails still activate at the same threshold.

Suggested tests:

- Add a Vitest benchmark-style test for appending 4,000 events in batches.
- Add a Playwright trace for opening a large session and toggling views.

## Task 8: Analytics Saved-Session Scan Reduction

Priority: P2

Primary files:

- `src/cc_deep_research/web_server_routes/misc_routes.py`
- `src/cc_deep_research/session_store.py`
- `src/cc_deep_research/telemetry/ingest.py`
- `tests/test_web_server_misc_routes.py`

Problem:

`/api/analytics` performs DuckDB aggregations, then scans saved session summaries and archived session summaries from disk.

Implementation outline:

1. Store archived state in DuckDB during telemetry ingestion when available.
2. If disk summaries remain the source of truth, scan them once and compute both archived and active counts.
3. Avoid a full saved-session scan when the analytics request only needs telemetry-derived data.

Acceptance criteria:

- `/api/analytics` does not read all summaries twice.
- Existing analytics payload shape remains unchanged.

Suggested tests:

- Build a fixture with many saved summaries and assert only one scan happens.
- Verify archived and active counts match current behavior.

