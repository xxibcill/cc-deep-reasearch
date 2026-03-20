# Dashboard Web Search Cache Tasks 03: Provider Integration

Status: Done

## Goal

Apply cache behavior consistently at the provider layer so all research execution modes benefit.

## Task Breakdown

### 5. Wrap provider execution with cache-aware search behavior

**Why**
The credit-saving logic should sit at the provider boundary, where all search requests already converge conceptually.

**Work**
- Add a cache-aware wrapper or decorator around `SearchProvider`
- On lookup:
  - return cache hit when valid
  - treat expired entries as misses
  - execute underlying provider on miss
  - store successful results with TTL
- Keep provider-specific code such as Tavily payload construction separate from cache policy

**Acceptance criteria**
- Repeated identical searches reuse cached results
- Misses still call the underlying provider normally
- Provider errors still surface correctly and do not poison the cache in v1

**Likely files**
- `src/cc_deep_research/providers/__init__.py`
- `src/cc_deep_research/providers/tavily.py`
- new: `src/cc_deep_research/providers/cached.py`

### 6. Centralize provider construction behind one factory

**Why**
The cache will be bypassed if some runtime paths instantiate providers directly and others do not.

**Work**
- Introduce one shared provider-construction function or factory
- Build raw providers there, then wrap them with cache support when enabled
- Replace ad hoc provider construction in existing collectors

**Acceptance criteria**
- Sequential and parallel search flows use the same provider factory
- Cache enablement is controlled in one place
- New providers can adopt the cache without copy-paste wiring

**Likely files**
- `src/cc_deep_research/agents/source_collector.py`
- `src/cc_deep_research/orchestration/source_collection_parallel.py`
- new: `src/cc_deep_research/providers/factory.py`

### 7. Ensure the parallel researcher path uses the cache

**Why**
Parallel mode is one of the most expensive paths and currently constructs Tavily directly.

**Work**
- Refactor parallel collection to request a provider from the shared factory
- Preserve current parallel behavior and result limits
- Verify cache keys still distinguish different parallel request shapes when needed

**Acceptance criteria**
- Parallel researcher tasks can hit the same cache as sequential runs
- No direct Tavily construction remains in the main research path unless explicitly justified

**Likely files**
- `src/cc_deep_research/orchestration/source_collection_parallel.py`
- `src/cc_deep_research/agents/researcher.py`

### 8. Add in-flight duplicate suppression for concurrent misses

**Why**
A persistent cache alone does not stop two identical concurrent misses from both spending credits before the first write completes.

**Work**
- Add an in-memory registry of active lookups keyed by the normalized request signature
- Reuse the same in-flight task for matching concurrent requests
- Clear in-flight state on success and failure

**Acceptance criteria**
- Concurrent identical searches during one process lifetime collapse to one upstream provider call
- Failed in-flight requests do not leave stuck entries behind

**Likely files**
- new: `src/cc_deep_research/providers/cached.py`
- new: `src/cc_deep_research/search_cache.py`
