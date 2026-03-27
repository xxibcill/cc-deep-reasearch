# Changelog

All notable changes to this project will be documented in this file.
The format is based on Keep a Changelog, and this project follows Semantic Versioning.
History before `0.1.0` is summarized from the repository state captured on 2026-03-11.

## [Unreleased]

<!-- Add Added/Changed/Fixed entries here before cutting a release. -->

### Completed Task Packs

#### Web Search Cache (6 tasks)

- Search cache configuration and identity rules (SearchCacheConfig, cache key normalization)
- SQLite-backed persistent cache store with serialization/deserialization
- Cache-aware provider wrapper with in-flight deduplication
- Cache telemetry metadata (cache_status, cache_key, cache_age_seconds, expires_at)
- Backend cache-management API routes (list, stats, purge, delete, clear)
- Dashboard cache settings UI and management panel with stats display

#### Dashboard Session Management (21 tasks)

Phase 1 - Session deletion from dashboard:
- Session history inventory and delete contract
- Session purge service with telemetry and DuckDB deletion helpers
- Saved session artifact deletion
- Delete session API and dashboard client integration
- Session list and page delete flows
- Deletion safety and validation

Phase 2 - Extended lifecycle management:
- Session summary enrichment and list query API
- Dashboard session list filters
- Active run stop API and dashboard flow
- Bulk session action contract and delete service/API
- Bulk delete dashboard flow
- Session archive and restore
- Retention reconciliation and audit
- Active session detection fix

#### Trace Contract Hardening (4 tasks)

- Hardened trace contract with versioned schema and semantic events (decision.made, state.changed, degradation.detected)
- Added derived trace APIs with cursor-paginated history access
- Added operator panels, run compare, and trace bundle export
- Added durable step checkpoints and resume execution support

#### Dashboard Config Editor (14 tasks)

- Added a shared backend config mutation service with atomic YAML patching and validation
- Added dashboard config read/write APIs exposing persisted vs effective config, override metadata, and masked secret fields
- Added a dashboard settings editor for core v1 fields, env override state, secret replace/clear flows, and post-save runtime guidance
- Added backend/frontend coverage and operator docs for config precedence, editable fields, and secret handling

#### Dashboard Agent Prompt Editor (10 tasks)

- Added a typed per-run `agent_prompt_overrides` contract and threaded it through research run preparation and runtime setup
- Added a centralized prompt registry/resolver with safe merge rules, size validation, and empty-override handling
- Added dashboard prompt editing for supported LLM-backed agents in the start research flow
- Persisted prompt overrides and effective prompt configuration in session metadata and exposed configured prompts in session detail UI
- Added backend/frontend test coverage and documented the v1 boundary for heuristic-only agents

#### Decision Graph Observability (30 tasks)

- Added a first-class backend-derived `decision_graph` contract with stable nodes, edges, and explicit-versus-inferred relationship markers
- Added decision-graph derivation to derived telemetry summaries and expanded explicit `decision.made` coverage across routing, planning, iteration, and degraded execution paths
- Added `decision_graph` delivery in live session detail, historical session detail, session API responses, and portable trace bundle exports
- Added a dedicated dashboard decision-graph view with node inspection, filters, zoom/pan, and explicit-versus-inferred styling
- Added fixtures, backend/API/export/UI tests, rollout phases, and operator-facing documentation for graph limits and telemetry coverage

## [0.1.0] - 2026-03-11

### Added

- Initial tracked release for the CC Deep Research CLI.
- Multi-stage research workflow with planning, source collection, analysis, validation, and reporting.
- Session persistence, telemetry ingestion, dashboard support, and a versioned benchmark corpus.

### Changed

- Established repository-level version tracking and a maintained changelog for future work history.
