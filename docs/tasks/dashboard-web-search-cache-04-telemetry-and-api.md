# Dashboard Web Search Cache Tasks 04: Telemetry and Backend API

## Goal

Expose cache behavior to operators and backend consumers through telemetry and explicit dashboard API routes.

## Task Breakdown

### 9. Add cache-aware telemetry

**Why**
Operators need proof that the cache is reducing cost, and developers need enough data to debug stale or bypassed behavior.

**Work**
- Extend search telemetry metadata with fields like:
  - `cache_status`
  - `cache_key`
  - `cache_age_seconds`
  - `expires_at`
- Add session summary counters such as:
  - `cache_hits`
  - `cache_misses`
  - `cache_bypasses`
  - `avoided_search_requests`

**Acceptance criteria**
- Search events distinguish hits from misses
- Summary metrics can support simple dashboard KPI displays later
- Existing telemetry consumers keep working when cache metadata is absent

**Likely files**
- `src/cc_deep_research/monitoring.py`
- `src/cc_deep_research/telemetry/ingest.py`
- `src/cc_deep_research/telemetry/query.py`

### 10. Add backend cache-management API contracts

**Why**
The dashboard needs typed endpoints for inspecting and managing cache state, not direct filesystem or database access.

**Work**
- Define request and response models for:
  - cache stats
  - cache list
  - delete one entry
  - purge expired entries
  - clear all entries
- Keep the API explicit about destructive actions

**Acceptance criteria**
- API responses return enough metadata for operator decisions
- Destructive actions are scoped and predictable
- Empty-cache behavior is clean

**Likely files**
- new: `src/cc_deep_research/cache_api_models.py` or `src/cc_deep_research/config/api_models.py`
- `src/cc_deep_research/web_server.py`

### 11. Add backend cache-management routes

**Why**
The dashboard needs runtime access to cache state and cache-control operations.

**Work**
- Add routes such as:
  - `GET /api/search-cache`
  - `GET /api/search-cache/stats`
  - `POST /api/search-cache/purge-expired`
  - `DELETE /api/search-cache/{entry_id}`
  - `DELETE /api/search-cache`
- Reuse the shared cache store instead of duplicating SQL in the route layer

**Acceptance criteria**
- Routes return stable JSON payloads
- Cache-management actions work when the cache database is missing or empty
- Errors are structured and operator-readable

**Likely files**
- `src/cc_deep_research/web_server.py`
- new: `src/cc_deep_research/search_cache.py` or `src/cc_deep_research/cache/store.py`
