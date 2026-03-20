# Dashboard Web Search Cache Tasks 06: Testing

## Goal

Cover cache behavior across backend execution, backend APIs, and dashboard UI so the feature is safe to iterate on.

## Task Breakdown

### 15. Add tests for backend cache behavior

**Why**
This feature crosses config, provider calls, serialization, expiry, and API routes. It will regress easily without targeted tests.

**Work**
- Test cache key normalization
- Test hit, miss, and expired-entry behavior
- Test concurrent duplicate suppression
- Test provider error behavior on misses
- Test cache-management routes
- Test config integration for cache settings

**Acceptance criteria**
- Tests cover both normal and failure paths
- Parallel and sequential entry points both exercise cache-enabled providers

**Likely files**
- `tests/test_tavily_provider.py`
- `tests/test_web_server.py`
- `tests/test_config.py`
- new: `tests/test_search_cache.py`

### 16. Add frontend tests for cache controls

**Why**
The dashboard will add new settings fields and destructive cache actions that should not rely only on manual testing.

**Work**
- Test cache settings request payload generation
- Test list rendering and empty-state behavior
- Test purge and clear confirmation flows
- Test inline error handling for cache actions

**Acceptance criteria**
- UI actions generate the expected API calls
- Failed cache actions surface readable feedback

**Likely files**
- `dashboard/src/components/config-editor.tsx`
- new frontend tests for `search-cache-panel`
