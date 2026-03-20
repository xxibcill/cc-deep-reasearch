# Dashboard Web Search Cache Tasks

## Goal

Add a reusable web search cache that prevents repeated provider calls for equivalent searches, expires cached entries after a configurable time window, and gives operators cache controls from the dashboard.

## Scope

- Cache provider search results before they consume external search API credits
- Reuse the same cache for browser-started runs, CLI runs, sequential collection, and parallel researchers
- Make cache expiry configurable through the existing dashboard settings flow
- Add dashboard visibility and cache-management actions for operators
- Add telemetry so cache value is measurable instead of inferred

## Non-Goals

- Caching arbitrary LLM completions
- Building a distributed cache service in v1
- Caching failed provider responses in v1
- Rewriting dashboard analytics around cache data in v1
- Perfect semantic query deduplication in v1

## Current Constraints

Search execution is not centralized in one call site today.

- Sequential collection goes through `SourceCollectorAgent`, which uses configured providers
- Parallel collection creates `TavilySearchProvider` directly and would bypass any cache added only to the normal collector path
- The dashboard already has a settings flow through `GET /api/config` and `PATCH /api/config`, so cache settings should reuse that mechanism instead of introducing a second configuration surface

Because of those constraints, the cache must be implemented in shared backend provider construction, not only in the dashboard frontend.

## Recommended v1 Decisions

- Use SQLite for persistent cache storage
- Cache only successful provider responses
- Use explicit TTL expiration with lazy expiry checks on read
- Add manual purge actions from the dashboard
- Include provider name and normalized search options in the cache key
- Return freshly deserialized result objects on cache hits so later provenance mutation does not leak across runs

## Task Files

1. [Config and Identity](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/dashboard-web-search-cache-01-config-and-identity.md)
2. [Storage and Serialization](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/dashboard-web-search-cache-02-storage-and-serialization.md)
3. [Provider Integration](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/dashboard-web-search-cache-03-provider-integration.md)
4. [Telemetry and Backend API](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/dashboard-web-search-cache-04-telemetry-and-api.md)
5. [Dashboard UI](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/dashboard-web-search-cache-05-dashboard-ui.md)
6. [Testing](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/dashboard-web-search-cache-06-testing.md)

## Recommended Delivery Order

1. Config and identity rules
2. Persistent store and serialization
3. Provider wrapper and shared factory
4. Parallel-path refactor and in-flight suppression
5. Telemetry and backend cache-management API
6. Dashboard settings and cache panel
7. Backend and frontend tests

## Risks To Watch

- Serving stale results too aggressively for time-sensitive queries
- Missing the parallel path and silently bypassing the cache in expensive runs
- Reusing mutable cached objects and contaminating provenance metadata across sessions
- Counting cache hits as full search calls in telemetry and obscuring actual savings
- Letting cache-management routes grow direct SQL logic instead of using a shared store
