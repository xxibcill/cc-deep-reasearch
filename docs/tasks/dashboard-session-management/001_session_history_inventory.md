# Task 001: Inventory Session History Storage Layers

Status: Done

## Objective

Document exactly what data constitutes one dashboard-visible session so deletion semantics are clear before any destructive UI is added.

## Storage Layers Overview

The dashboard displays sessions from **three distinct storage layers**, each with different characteristics:

```
~/.config/cc-deep-research/
├── sessions/              # Layer 1: Saved Session Files (JSON)
│   └── {session_id}.json
├── telemetry/            # Layer 2: Live Telemetry Files (JSONL + JSON)
│   └── {session_id}/
│       ├── events.jsonl
│       └── summary.json
└── telemetry.duckdb     # Layer 3: Analytics Database (SQL)
    ├── telemetry_sessions
    └── telemetry_events
```

---

## Layer 1: Saved Session Files (session_store.py)

**Location:** `<config_dir>/sessions/` (default: `~/.config/cc-deep-research/sessions/`)

| Attribute | Value |
|-----------|-------|
| Required | Always expected |
| Format | JSON files |
| Filename | `{session_id}.json` |
| Created by | `SessionStore.save_session()` |

### Contents

- `session_id`: Unique session identifier
- `query`: Original research query
- `depth`: Research depth (quick/standard/deep)
- `started_at`: Session start timestamp
- `completed_at`: Session completion timestamp
- `searches[]`: All search operations with results
- `sources[]`: All collected source items with content
- `metadata`: Session metadata

### Key Functions

- `SessionStore.save_session()` - Persists complete session to JSON
- `SessionStore.load_session()` - Retrieves session from disk
- `SessionStore.list_sessions()` - Lists sessions with metadata
- `SessionStore.delete_session()` - Deletes single JSON file

---

## Layer 2: Live Telemetry Files (telemetry/live.py)

**Location:** `<config_dir>/telemetry/` (default: `~/.config/cc-deep-research/telemetry/`)

| Attribute | Value |
|-----------|-------|
| Required | Optional (requires `--telemetry` flag) |
| Format | JSONL + JSON |
| Directory | `<telemetry_dir>/{session_id}/` |
| Created by | `WorkflowMonitor` during execution |

### Per-Session Files

#### events.jsonl

One JSON object per line with telemetry events:
- `event_id`, `parent_event_id`, `sequence_number`
- `session_id`, `timestamp`
- `event_type` (e.g., "session.started", "phase.ended")
- `category` (e.g., "agent", "phase", "system")
- `name`, `status`, `duration_ms`
- `agent_id`, `metadata`

#### summary.json

Session-level aggregates:
- `session_id`, `status`, `created_at`
- `total_sources`, `total_time_ms`
- `instances_spawned`, `search_queries`, `tool_calls`
- `llm_prompt_tokens`, `llm_completion_tokens`, `llm_total_tokens`
- `providers[]`, `summary_json`

### Key Functions

- `query_live_sessions()` - Lists all telemetry directories
- `query_live_session_detail()` - Reads events.jsonl + summary.json
- `get_default_telemetry_dir()` - Returns telemetry base path

---

## Layer 3: DuckDB Analytics (telemetry/ingest.py, telemetry/query.py)

**Location:** `<config_dir>/telemetry.duckdb` (default: `~/.config/cc-deep-research/telemetry.duckdb`)

| Attribute | Value |
|-----------|-------|
| Required | Optional (requires `duckdb` dependency) |
| Format | DuckDB database |
| Created by | `ingest_telemetry_to_duckdb()` |

### Tables

#### telemetry_sessions

| Column | Type | Description |
|--------|------|-------------|
| session_id | VARCHAR | Primary key |
| status | VARCHAR | Session status |
| total_sources | INTEGER | Source count |
| total_time_ms | INTEGER | Total duration |
| instances_spawned | INTEGER | Claude instances |
| search_queries | INTEGER | Search count |
| tool_calls | INTEGER | Tool invocation count |
| llm_prompt_tokens | INTEGER | Prompt tokens used |
| llm_completion_tokens | INTEGER | Completion tokens |
| llm_total_tokens | INTEGER | Total LLM tokens |
| providers_json | VARCHAR | JSON array of providers |
| created_at | TIMESTAMP | Session start time |
| summary_json | VARCHAR | Full summary JSON |

#### telemetry_events

| Column | Type | Description |
|--------|------|-------------|
| event_id | VARCHAR | Event identifier |
| parent_event_id | VARCHAR | Parent event |
| sequence_number | INTEGER | Event order |
| session_id | VARCHAR | Session reference |
| timestamp | TIMESTAMP | Event time |
| event_type | VARCHAR | Event category |
| category | VARCHAR | Event category |
| name | VARCHAR | Event name |
| status | VARCHAR | Event status |
| duration_ms | INTEGER | Event duration |
| agent_id | VARCHAR | Agent identifier |
| metadata_json | VARCHAR | Event metadata |

### Key Functions

- `ingest_telemetry_to_duckdb()` - Imports telemetry JSONL → DuckDB
- `query_dashboard_data()` - Reads analytics for dashboard
- `get_default_dashboard_db_path()` - Returns DuckDB path

---

## Dashboard Session Assembly (web_server.py)

The `/api/sessions` endpoint merges data from Layer 2 and Layer 3:

```
1. Query live sessions from telemetry/ (Layer 2)
   └─ query_live_sessions()

2. Query historical sessions from DuckDB (Layer 3)
   └─ query_dashboard_data() → sessions

3. Merge by session_id:
   - Live data takes precedence for active sessions
   - Historical data fills in completed sessions
   - Fields merged: status, total_time_ms, total_sources, created_at
```

### API Response Fields

| Field | Source | Notes |
|-------|--------|-------|
| session_id | Both | Primary key |
| created_at | Layer 2 or 3 | Earliest timestamp |
| total_time_ms | Layer 2 or 3 | Duration in ms |
| total_sources | Layer 2 or 3 | Source count |
| status | Layer 2 or 3 | "running" / "completed" |
| active | Layer 2 only | True if running |
| event_count | Layer 2 only | Live event count |
| last_event_at | Layer 2 only | Latest event timestamp |

---

## Current Gaps

### 1. Stale Telemetry Directories

**Issue:** Telemetry directories remain in `<telemetry_dir>/` after session completion if the process crashes or is interrupted.

**Evidence:** `query_live_sessions()` detects active sessions by checking for `summary.json` absence + no `session.finished` event. Orphaned directories without summary.json appear as "active" but are stuck.

### 2. Partial Session Cleanup

**Issue:** `SessionStore.delete_session()` only removes the JSON file (Layer 1). It does **not** clean up:
- Telemetry directory (Layer 2)
- DuckDB records (Layer 3)

**Evidence:** `session_store.py:151-166` only calls `path.unlink()` on the JSON file.

### 3. DuckDB Staleness

**Issue:** DuckDB is not automatically updated. Sessions exist in telemetry/ but not in telemetry.duckdb until `ingest_telemetry_to_duckdb()` is manually or periodically run.

**Evidence:** `web_server.py:376` calls `query_dashboard_data()` but never triggers ingestion.

### 4. No Cross-Layer Foreign Keys

**Issue:** Session deletion in Layer 1 does not cascade to Layers 2 and 3.

**Evidence:** Each layer operates independently with no referential integrity.

---

## Deletion Semantics Implications

For any future "Delete Session" UI feature:

| Layer | Delete Action | Complexity |
|-------|----------------|------------|
| Layer 1 | `unlink(session_id.json)` | Simple - single file |
| Layer 2 | `rmtree(telemetry/session_id/)` | Medium - directory cleanup |
| Layer 3 | `DELETE FROM telemetry_* WHERE session_id=?` | Medium - requires DuckDB |

**Recommended:** Delete must operate on all three layers simultaneously to ensure complete removal.

---

## Suggested Verification

To verify this inventory against the codebase:

1. **Layer 1 verification:**
   ```bash
   ls ~/.config/cc-deep-research/sessions/*.json | head -5
   cat ~/.config/cc-deep-research/sessions/<session_id>.json | jq '.session_id'
   ```

2. **Layer 2 verification:**
   ```bash
   ls ~/.config/cc-deep-research/telemetry/
   cat ~/.config/cc-deep-research/telemetry/<session_id>/events.jsonl | head -1
   cat ~/.config/cc-deep-research/telemetry/<session_id>/summary.json
   ```

3. **Layer 3 verification:**
   ```bash
   duckdb ~/.config/cc-deep-research/telemetry.duckdb \
     "SELECT session_id, status FROM telemetry_sessions LIMIT 5;"
   ```

4. **API verification:**
   ```bash
   curl http://localhost:8501/api/sessions | jq '.sessions[:2]'
   ```

## Dependencies

- none

## Acceptance Criteria

- [x] contributors can point to every storage location that must be considered during delete
- [x] the difference between saved session artifacts and dashboard telemetry history is written down explicitly
- [x] follow-on tasks do not need to rediscover where session data lives
