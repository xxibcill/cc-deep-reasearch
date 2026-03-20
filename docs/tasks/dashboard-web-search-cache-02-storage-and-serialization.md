# Dashboard Web Search Cache Tasks 02: Storage and Serialization

Status: Done

## Goal

Persist cache entries safely and reconstruct valid runtime search-result objects from stored rows.

## Task Breakdown

### 3. Implement a persistent cache store

**Why**
The cache must survive process restarts and be queryable by the dashboard.

**Work**
- Add a SQLite-backed store with schema creation on first use
- Persist:
  - cache key
  - provider
  - normalized query
  - request signature
  - serialized `SearchResult`
  - `created_at`
  - `expires_at`
  - `last_accessed_at`
  - `hit_count`
- Add helper methods for get, put, delete, and purge-expired

**Acceptance criteria**
- Cache entries persist across runs
- Expired entries are detectable without corrupting valid entries
- Store API is small and testable

**Likely files**
- new: `src/cc_deep_research/search_cache.py` or `src/cc_deep_research/cache/store.py`

### 4. Add cache serialization and deserialization for search results

**Why**
Provider results are Pydantic models with nested metadata. Cache reads must return valid runtime objects, not raw dicts.

**Work**
- Serialize `SearchResult` and nested `SearchResultItem` payloads in a stable format
- Deserialize cached rows back into runtime models
- Preserve provider metadata and timestamps where useful
- Ensure cache-hit objects are fresh instances

**Acceptance criteria**
- Cached results round-trip without losing required fields
- A cache hit returns a valid `SearchResult`
- Mutating cache-hit results later in the pipeline does not mutate stored payloads

**Likely files**
- new: `src/cc_deep_research/search_cache.py` or `src/cc_deep_research/cache/serialization.py`
- `src/cc_deep_research/models/search.py`
