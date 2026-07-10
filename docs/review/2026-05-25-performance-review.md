# Performance Review - 2026-05-25

This review covers the current `cc-deep-research` repository with emphasis on backend latency, live telemetry scale, knowledge retrieval, and dashboard render cost.

Scope note: GitNexus MCP resources were not exposed in this session, and `npx gitnexus status` failed with `Cannot destructure property 'package' of 'node.target' as it is null.` This report is based on static source inspection. No production profiling was run.

## Summary

Overall score: 11/20.

No P0 blocking performance defects were found. The main risk is that several "paged" or "summary" paths still load and derive full-session data. This is acceptable for small local datasets, but it will become slow and memory-heavy as telemetry sessions, graph nodes, benchmark runs, and content-gen records grow.

Priority counts:

- P1 major: 3
- P2 minor but important: 4
- P3 polish: 1

## P1 Findings

### P1-1: Session list loads too much live telemetry

Location:

- `src/cc_deep_research/web_server_routes/session_routes.py:296`
- `src/cc_deep_research/telemetry/live.py:221`
- `src/cc_deep_research/telemetry/live.py:346`
- `src/cc_deep_research/telemetry/live.py:301`

Current behavior:

- `GET /api/sessions` calls `query_live_sessions()` before pagination and before saved/historical filtering.
- `query_live_sessions()` iterates every telemetry session directory.
- For each live session directory, `_read_live_session_snapshot()` reads the full `events.jsonl` file into memory when the file cache key changes.
- `_is_session_truly_active()` may open DuckDB per session to check whether the session already exists in historical telemetry.
- `_LIVE_SESSION_CACHE` is process-global and unbounded.

Impact:

- The session list can become O(total sessions * full event-file size), even though the API returns a small page of rows.
- Dashboard landing and monitor list views can stall when many old telemetry folders exist.
- Long-running processes can retain large snapshots indefinitely because the cache has no eviction.

Suggested fix:

- Introduce a lightweight live-session summary reader that only uses `summary.json`, file metadata, and the last event line.
- Batch historical DuckDB status lookup for all candidate session IDs instead of opening one connection per session.
- Apply limit/filtering before parsing full event files.
- Bound `_LIVE_SESSION_CACHE` with size or TTL eviction, or split it into summary and detail caches.

Verification ideas:

- Add a slow/perf test with 500 telemetry dirs and 1,000 events each. `query_live_sessions(limit=100)` should not parse all event payloads.
- Assert that the number of DuckDB connections is not proportional to session count.

### P1-2: Event pagination still builds full-session outputs

Location:

- `src/cc_deep_research/web_server_routes/session_routes.py:964`
- `src/cc_deep_research/telemetry/live.py:501`
- `src/cc_deep_research/telemetry/live.py:540`
- `src/cc_deep_research/telemetry/live.py:568`
- `src/cc_deep_research/telemetry/live.py:570`
- `src/cc_deep_research/telemetry/live.py:574`

Current behavior:

- `GET /api/sessions/{session_id}/events` passes `include_derived=False`, but it still calls `_query_session_api_detail()`, which calls `query_live_session_detail()`.
- `query_live_session_detail()` copies all snapshot events, builds an event page, then also returns `event_tail`, `agent_timeline`, `event_tree`, `subprocess_streams`, `llm_route_analytics`, and `active_phase`.
- These derived structures are built even when the endpoint only returns the paged events payload.

Impact:

- Cursor pagination reduces response size, but not CPU or memory cost on live-session files.
- A request for 100 events can still pay the cost of scanning and deriving thousands of events.
- WebSocket history requests have the same issue through `web_server_routes/websocket_adapter.py:212`.

Suggested fix:

- Add `query_live_events_page(session_id, cursor, before_cursor, limit)` that only reads enough event records to build the requested page and total count.
- Add `query_historical_events_page()` if the DuckDB path needs a matching API.
- Update `/api/sessions/{session_id}/events` and WebSocket `get_history` to use the page-specific function.
- Keep `query_live_session_detail()` for full detail pages only.

Verification ideas:

- Add a test that monkeypatches `build_event_tree`, `build_subprocess_streams`, and `build_llm_route_streams`; `/events` should not call them.
- Add a live telemetry performance test for a 20,000 event file with `limit=100`.

### P1-3: Telemetry writes and ingestion are row-by-row

Location:

- `src/cc_deep_research/monitoring.py:96`
- `src/cc_deep_research/monitoring.py:311`
- `src/cc_deep_research/monitoring.py:318`
- `src/cc_deep_research/event_router.py:131`
- `src/cc_deep_research/telemetry/ingest.py:155`
- `src/cc_deep_research/telemetry/ingest.py:192`

Current behavior:

- `ResearchMonitor` stores every telemetry payload in `_telemetry_events`.
- Each event append opens the JSONL file, writes one line, and closes the file.
- Each event publishes through an unbounded `asyncio.create_task()`.
- DuckDB ingestion deletes and inserts event rows one at a time, after indexes are already created.

Impact:

- High-volume telemetry sessions can spend significant time in filesystem open/write/close loops.
- Long runs retain all events in memory until completion.
- Slow or disconnected WebSocket clients can create many publish tasks.
- Re-ingestion cost grows linearly with Python/DuckDB round trips instead of using DuckDB bulk ingestion.

Suggested fix:

- Keep a persistent file handle or add a small buffered writer for monitor JSONL events.
- Make in-memory event retention optional or bounded after summary fields have been accounted for.
- Add bounded per-session publish queues or coalesced WebSocket batches.
- In `ingest_telemetry_to_duckdb()`, accumulate rows and use `executemany`, a DuckDB appender, or staged JSON import.
- Create indexes after bulk loading when building a new database.

Verification ideas:

- Add a perf gate for 100,000 emitted events with persistence enabled.
- Add a perf gate for ingesting at least 100,000 JSONL events.

## P2 Findings

### P2-1: Blocking work runs inside async routes

Location:

- `src/cc_deep_research/web_server_routes/knowledge_routes.py:207`
- `src/cc_deep_research/web_server_routes/knowledge_routes.py:523`
- `src/cc_deep_research/web_server_routes/misc_routes.py:786`
- `src/cc_deep_research/web_server_routes/misc_routes.py:500`
- `src/cc_deep_research/web_server_routes/misc_routes.py:618`

Current behavior:

- Several FastAPI async routes directly perform filesystem scans, JSON reads, SQLite work, or multi-session ingestion.
- `POST /api/knowledge/backfill` loops session files and calls `ingest_session()` synchronously inside the request.
- Benchmark and knowledge list/detail endpoints perform blocking disk reads inside async handlers.

Impact:

- One large backfill or slow filesystem scan can block the event loop and delay unrelated dashboard requests.
- Operators receive no progress stream for long work beyond the final response.

Suggested fix:

- Move backfill and rebuild work to background jobs with status polling.
- Wrap medium-cost filesystem work in `asyncio.to_thread()` or make the route sync if it is intentionally blocking.
- Add request limits and response pagination for file-backed list endpoints.

Verification ideas:

- Add tests using a fake slow `ingest_session()` to ensure the route returns quickly with a job ID.
- Add an integration test where a light endpoint remains responsive while a backfill is running.

### P2-2: Knowledge graph retrieval ignores available indexes

Location:

- `src/cc_deep_research/knowledge/retrieval.py:159`
- `src/cc_deep_research/knowledge/retrieval.py:176`
- `src/cc_deep_research/knowledge/graph_index.py:113`
- `src/cc_deep_research/web_server_routes/knowledge_routes.py:437`
- `src/cc_deep_research/web_server_routes/knowledge_routes.py:449`

Current behavior:

- `KnowledgeRetrievalService.retrieve_context()` calls `index.all_nodes()` and tokenizes labels/properties for every node on every query.
- Node-neighbor lookup calls `index.all_edges()` and then performs one `index.node()` lookup per neighbor.
- SQLite has indexes on node kind, edge source, and edge target, but these paths do not use source/target queries.

Impact:

- Retrieval and graph expansion scale linearly with full graph size.
- Large knowledge vaults will make planning and graph browsing progressively slower.

Suggested fix:

- Add `GraphIndex.edges_for_node(node_id)` using `WHERE source_id = ? OR target_id = ?`.
- Add `GraphIndex.nodes_by_ids(ids)` for batched neighbor loading.
- Add SQLite FTS or a token table for labels/properties, with query-time candidate narrowing before scoring.
- Bound explanation payloads and score maps to selected nodes.

Verification ideas:

- Add a benchmark fixture with 50,000 nodes and 200,000 edges.
- Assert neighbor lookup is not implemented via `all_edges()` in tests, or benchmark it against a fixed latency budget.

### P2-3: Dashboard recomputes derived telemetry aggressively

Location:

- `dashboard/src/hooks/useDashboard.ts:306`
- `dashboard/src/lib/websocket.ts:219`
- `dashboard/src/lib/websocket.ts:225`
- `dashboard/src/components/session-details.tsx:240`
- `dashboard/src/components/session-details.tsx:250`
- `dashboard/src/components/session-details.tsx:254`
- `dashboard/src/components/session-details.tsx:283`
- `dashboard/src/lib/telemetry-transformers.ts:804`

Current behavior:

- Incoming history and live events are appended into Zustand and sorted on each buffered update.
- `SessionDetails` derives full telemetry state, filters events, derives telemetry state again for the filtered list, and derives operator insights.
- The store trims to `MAX_BUFFERED_EVENTS = 4000`, but the derivation cost is still paid repeatedly for graph, timeline, tool, LLM, filters, and insights.
- The WebSocket opens by requesting 1,000 history events even when the initial view may not need that many.

Impact:

- The UI can jank under high-frequency live streams or large history loads.
- Filtering and view switches recompute full derived state in the main thread.

Suggested fix:

- Maintain incremental event indexes/counts in the store instead of rebuilding all derived views on each append.
- Move graph/timeline derivation to a Web Worker or defer it until the graph view is active.
- Request a smaller first history page and load more on demand.
- Avoid sorting when incoming sequence numbers are already monotonic.

Verification ideas:

- Add a Vitest benchmark for appending 4,000 events in batches.
- Add a Playwright trace for opening a 4,000 event session and switching filters/views.

### P2-4: Analytics route mixes DuckDB aggregation with full saved-session scan

Location:

- `src/cc_deep_research/web_server_routes/misc_routes.py:56`
- `src/cc_deep_research/web_server_routes/misc_routes.py:190`
- `src/cc_deep_research/session_store.py:247`
- `src/cc_deep_research/session_store.py:367`

Current behavior:

- `_query_analytics_data()` does aggregate DuckDB queries, then calls `SessionStore().list_sessions()` and `get_archived_session_ids()`.
- `list_sessions()` sorts every saved session JSON file by mtime and reads each summary.
- `get_archived_session_ids()` scans every summary JSON file again.

Impact:

- `/api/analytics` cost is proportional to all saved sessions, not only the selected DuckDB time window.
- The route duplicates work after already querying DuckDB.

Suggested fix:

- Store archived state in DuckDB ingestion or a small session-summary index.
- Reuse one summary scan if disk state is still needed.
- Push active/archived counts into DuckDB where possible.

Verification ideas:

- Add a perf test with 10,000 saved summaries and verify `/api/analytics?days_back=1` does not read every file twice.

## P3 Finding

### P3-1: Benchmark run endpoint is synchronous inside the API path

Location:

- `src/cc_deep_research/web_server_routes/misc_routes.py:532`
- `src/cc_deep_research/web_server_routes/misc_routes.py:563`
- `src/cc_deep_research/benchmark.py:345`
- `src/cc_deep_research/benchmark.py:417`

Current behavior:

- `POST /api/benchmarks/run` loads the corpus and runs the full benchmark before returning.
- The case runner uses an executor but immediately blocks on `.result()` for each case.
- The benchmark harness runs cases sequentially.

Impact:

- This is acceptable for a local operator tool, but poor for dashboard responsiveness.
- Long benchmark runs can tie up request handling and provide no progress beyond the final response.

Suggested fix:

- Convert benchmark runs into background jobs with progress and cancellation.
- Add bounded parallelism only if provider limits allow it.

Verification ideas:

- Add a route test proving the endpoint returns `202 Accepted` and a job ID quickly.

## Existing Good Patterns To Keep

- Search provider caching includes persistent SQLite cache identity and in-flight miss de-duplication: `src/cc_deep_research/providers/cached.py:41`.
- DuckDB telemetry queries already have useful indexes, including `(session_id, sequence_number)`: `src/cc_deep_research/telemetry/ingest.py:155`.
- Derived live summaries are cached in `telemetry/summary_cache.py`.
- The dashboard already caps live buffered events through `MAX_BUFFERED_EVENTS`.
- SQLite backlog storage uses WAL and a process-local lock, which is a better direction than YAML for frequently edited state.

## Suggested Fix Order

1. Fix live event pagination and WebSocket history first. This directly reduces dashboard latency and payload work.
2. Fix session list live summary loading and cache bounds. This improves every dashboard entry point.
3. Batch telemetry writes/ingestion. This improves run-time overhead and replay costs.
4. Add knowledge graph indexed accessors and retrieval candidate narrowing.
5. Move long-running API work to background jobs.
6. Optimize dashboard derivation after backend paging semantics are lighter.
