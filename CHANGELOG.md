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

#### Dashboard shadcn Migration (13 tasks)

- Defined a staged migration plan for the Next.js dashboard, preserving custom graph and timeline renderers while standardizing the shell around them
- Replaced and expanded the shared `ui/` primitive layer and field-shell patterns for forms, dialogs, tabs, tables, alerts, filters, and navigation
- Migrated the start-research flow, home/session list, settings surfaces, session workspace, session filters/table, and content-studio shell onto the shared shadcn-style vocabulary
- Completed content-studio form and data-panel migration, then closed the rollout with regression review, accessibility/visual-consistency checks, cleanup, and documentation updates

#### Decision Graph Observability (30 tasks)

- Added a first-class backend-derived `decision_graph` contract with stable nodes, edges, and explicit-versus-inferred relationship markers
- Added decision-graph derivation to derived telemetry summaries and expanded explicit `decision.made` coverage across routing, planning, iteration, and degraded execution paths
- Added `decision_graph` delivery in live session detail, historical session detail, session API responses, and portable trace bundle exports
- Added a dedicated dashboard decision-graph view with node inspection, filters, zoom/pan, and explicit-versus-inferred styling
- Added fixtures, backend/API/export/UI tests, rollout phases, and operator-facing documentation for graph limits and telemetry coverage

#### Content Generation Pipeline Upgrade (7 tasks)

- Added an `OpportunityBrief` planning contract, `plan_opportunity` stage, new planning agent/prompt, and supporting documentation/tests for the upgraded content-generation flow
- Added `PipelineStageTrace` persistence with compact input/output summaries, skipped/failed/degraded coverage, and live per-stage router events that reflect execution order
- Hardened backlog and scoring stages with degraded-state signaling, empty-input short-circuiting, and trace warnings when parsing yields sparse or malformed results
- Replaced first-hit idea selection with explicit shortlist metadata (`selected_idea_id`, `selection_reasoning`, `runner_up_idea_ids`) and downstream chosen-idea resolution
- Aligned the dashboard pipeline view and client types with backend shortlist/degraded-state fields so operators can inspect selection rationale and stage health directly
- Added fixture-backed content-generation smoke coverage plus router/API regressions for live stage events and completed browser-started runs

#### Content-Gen Dashboard Detail Upgrade (7 tasks)

- Refactored the pipeline detail screen around stage-specific panels so each pipeline stage can render and evolve independently without a large page-level switch
- Expanded ideation and downstream stage views to surface full backlog, scoring, angle, research, packaging, publish, QC, and performance-analysis detail already present in `PipelineContext`
- Integrated the reusable scripting process inspector into the pipeline detail page alongside final-script metadata such as execution mode, pass count, hook rationale, and word count
- Added live pipeline-context propagation through stage-completion, skip, and failure WebSocket events so active runs progressively refresh stage detail without manual refetching
- Enriched backend/frontend stage-trace metadata and decision summaries with structured operator signals including selected artifacts, proof/fact counts, cache reuse, scripting counts, warnings, and rerun-research state
- Expanded backend and Playwright regression coverage for richer detail rendering, live context refresh, and stage-event payloads
- Updated operator-facing docs for the pipeline detail page, live monitoring behavior, and stage-trace visibility

### Removed

- Removed completed task-planning documents from `docs/tasks/` after consolidating their delivered work into this changelog, including the dashboard-detail upgrade task pack

## [0.1.0] - 2026-03-11

### Added

- Initial tracked release for the CC Deep Research CLI.
- Multi-stage research workflow with planning, source collection, analysis, validation, and reporting.
- Session persistence, telemetry ingestion, dashboard support, and a versioned benchmark corpus.

### Changed

- Established repository-level version tracking and a maintained changelog for future work history.
