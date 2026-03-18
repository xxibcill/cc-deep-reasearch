# Task 001: Inventory Session History Storage Layers

Status: Planned

## Objective

Document exactly what data constitutes one dashboard-visible session so deletion semantics are clear before any destructive UI is added.

## Scope

- trace where session data is stored today across saved session files, telemetry directories, and DuckDB analytics
- identify which storage layers are optional versus always expected
- document how browser dashboard rows are assembled from those layers
- note current gaps, including stale telemetry and partial session cleanup behavior

## Target Files

- `docs/tasks/dashboard-session-management/001_session_history_inventory.md`
- `src/cc_deep_research/session_store.py`
- `src/cc_deep_research/telemetry/live.py`
- `src/cc_deep_research/telemetry/ingest.py`
- `src/cc_deep_research/web_server.py`

## Dependencies

- none

## Acceptance Criteria

- contributors can point to every storage location that must be considered during delete
- the difference between saved session artifacts and dashboard telemetry history is written down explicitly
- follow-on tasks do not need to rediscover where session data lives

## Suggested Verification

- review the resulting inventory against the current dashboard list, detail, and report code paths
