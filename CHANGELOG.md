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

#### Dashboard Operator Workspace Upgrade (10 tasks)

- Normalized the dashboard visual system across home, session overview, monitor, report, compare, and settings surfaces so the app reads as one operator-focused product
- Reworked the home page into a control room with clearer active-run, attention-needed, and recent-outcome triage while keeping launch actions available without dominating the page
- Built a unified session workspace shell spanning Overview, Monitor, and Report routes with stronger shared framing, route switching, and session identity/status context
- Redesigned the session overview into an operator summary that highlights execution state, evidence, artifacts, technical facts, and likely next actions instead of a raw metadata dump
- Integrated monitor and report panels into the same workspace model with calmer framing, consistent loading/empty/failure states, and better first-screen orientation
- Added deterministic operator insights and next-step guidance derived from telemetry so common session-health questions are answerable without scanning the full event stream first
- Improved the launch flow with clearer presets, better progressive disclosure, and less intimidating access to advanced prompt overrides
- Tightened historical triage and two-session comparison flows so compare mode, compare outputs, and session-state cues are easier to enter and interpret
- Refreshed dashboard Playwright coverage, accessibility checks, screenshots, and operator-facing docs to match the upgraded home, workspace, and compare flows
- Clarified settings/runtime override behavior so persisted values, environment-shadowed fields, future-run impact, and secret flows are easier for operators to understand

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

#### Decision Graph Backend Derivation (5 tasks)

- Added typed graph structures for nodes, edges, and summary metadata with explicit support for inferred relationships
- Implemented `build_decision_graph(events)` deriving nodes from `decision.made`, `state.changed`, `degradation.detected`, and failure events
- Defined inference boundary with documented explicit versus inferred edge rules favoring correctness over graph density
- Extended derived summary to always include `decision_graph` with stable empty graph shape for sessions without data

#### Decision Graph API And Bundle (6 tasks)

- Added `decision_graph` to live and historical session detail endpoints with empty graph payload for no-derived mode
- Threaded `decision_graph` through the session detail API response with backward compatibility for existing consumers
- Added `decision_graph` to frontend TypeScript types and API client mapping
- Included `decision_graph` in portable trace bundle exports with schema version handling

#### Decision Graph Emission Coverage (6 tasks)

- Added explicit `decision.made` events for LLM routing decisions including route selection, fallback, and retry routes
- Added decision emission for iteration control (continue/stop/follow-up), provider state changes, and planner decomposition
- Standardized decision payload conventions across routing, planning, and iteration flows with consistent metadata fields
- Added focused emission tests verifying explicit decision events with useful metadata and real cause event links

#### Decision Graph Dashboard UI (6 tasks)

- Added typed `DecisionGraphNode`, `DecisionGraphEdge`, and `DecisionGraph` to dashboard model and session-detail response types
- Created dedicated `DecisionGraph` component with click-to-inspect, label/color by kind, inferred-edge styling, and zoom/pan
- Exposed decision graph in session details with new view mode and shared event inspector integration
- Added decision-specific filters for type, actor, severity, and explicit versus inferred differentiation

#### Decision Graph Tests And Rollout (7 tasks)

- Added backend derivation fixtures covering route selection, continue/stop iteration, degraded execution, and planner choices
- Added backend correctness tests verifying node/edge counts, explicit/inferred flags, cause links, and empty graph output
- Added API contract tests for session detail and trace bundle export including `include_derived=false` suppression
- Documented rollout phases and graph limits with explicit versus inferred link guidance for operators

#### Dashboard Config Editor (14 tasks)

- Added shared backend config mutation service with atomic YAML patching, validation, and CLI/non-CLI helper separation
- Added dashboard config API contract with persisted vs effective config, override metadata, and masked secret fields
- Added `GET /api/config` and `PATCH /api/config` endpoints with partial update support and env-override conflict handling
- Added settings page with v1 editable fields, env override state visibility, secret replace/clear flows, and post-save runtime guidance
- Added backend and frontend test coverage with docs for config precedence, editable fields, and secret handling

#### Dashboard Agent Prompt Editor (10 tasks)

- Added typed `agent_prompt_overrides` contract threaded through research run preparation and runtime setup
- Added centralized prompt registry/resolver with safe merge rules, size validation, and empty-override handling
- Added dashboard prompt editing for LLM-backed agents (analyzer, deep_analyzer, report_quality_evaluator) in start research flow
- Persisted prompt overrides and effective prompt configuration in session metadata with configured prompts exposed in session detail UI
- Added backend/frontend test coverage and documented v1 boundary for heuristic-only agents (lead, expander, validator)

#### Content Generation Expert Workflow (20 tasks)

- Added expert strategy models with evidence requirements, structured research pack with source provenance, and source retention through pipeline
- Added argument map models, prompts, agent, and parsing with pipeline wiring for structured argumentation
- Added scripting grounded with proof links, expert quality evaluator metrics, and QC claim safety review
- Added search query families, freshness metadata, multi-lane shortlist fanout, and tolerant stage degraded metadata
- Added retrieval fanout redesign, source authority scoring, evidence ranking, end-to-end claim traceability ledger
- Added targeted revision loop for weak beats, competitive differentiation check, and performance feedback into strategy memory and backlog

#### Backlog Management (16 tasks)

- Added persistent backlog source of truth with dedicated API contract and dashboard TypeScript types aligned with Python models
- Added backlog client, store state management, and dedicated backlog page shell with list/filter experience
- Added existing item actions (update, select, archive, delete) with edit and create flows wired to backend services
- Added full CRUD support with create endpoint, service support, and UI flow for backlog item creation
- Added content studio navigation cleanup, backend and frontend API/Dashboard test coverage

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

#### Dashboard Operator Workflow Refinements (9 tasks)

- Improved search-cache operations with clearer health framing, lower-risk destructive-action messaging, and stronger cache-state guidance for operators
- Added lightweight saved views for session-list and telemetry filters so frequent dashboard workflows can be reapplied without rebuilding state each time
- Hardened live monitoring with clearer connected, reconnecting, historical-only, and failed-stream states plus safer event buffering during reconnect
- Improved telemetry workspace responsiveness for larger sessions through targeted performance work on heavy event and graph views
- Made the decision graph easier to interpret with clearer affordances for explicit versus inferred links, higher-signal graph framing, and tighter inspector flow
- Expanded cross-session comparison beyond raw pairwise deltas with more actionable summaries and stronger baseline-selection workflows
- Added a more coherent dashboard notification model for long-running, destructive, and settings-related actions, including clearer completion and failure feedback
- Strengthened the bridge from research sessions into content-studio workflows so report-ready research outputs lead more naturally into downstream content work
- Extracted and hardened reusable dashboard design-system patterns to reduce visual drift and make future operator-surface work easier to extend

#### Dashboard Operator Enablement Expansion (10 tasks)

- Added a session-workspace trace-bundle export flow with explicit bundle-scope options so operators can download portable session bundles directly from the dashboard
- Exposed benchmark corpus metadata and recent benchmark outputs in a dedicated dashboard surface so evaluation workflows no longer depend on CLI-only access
- Added research-theme and workflow-preset selection to the launch flow while preserving a simple auto-detect default path for operators who do not need manual control
- Improved session lifecycle and retention controls with clearer archived-versus-purgeable framing, safer cleanup affordances, and stronger destructive-action guidance
- Added an artifact explorer with provenance-oriented summaries so operators can see which session artifacts exist, how they were produced, and which expected outputs are missing
- Expanded prompt-override inspection into a prompt experiment audit surface with clearer applied-defaults visibility and easier cross-run prompt-diff analysis
- Added a command palette and discoverable keyboard shortcuts for high-value dashboard navigation and workspace actions without breaking form input or confirmations
- Introduced lightweight onboarding and contextual help across high-density operator surfaces so first-time users can learn the workflow without slowing experienced users down
- Added a historical analytics dashboard with aggregate operational metrics, trend views, and drill-down paths back into session history for system-level monitoring
- Formalized a dashboard fixture and scenario library so Playwright and related regression tests can target named operator states consistently as the UI grows

#### Session Metadata and Type Safety (8 tasks)

- Documented the exact metadata shape produced by the research pipeline today with required versus optional field calls-outs
- Replaced ambiguous metadata dictionaries with explicit `TypedDict` contracts for strategy, analysis, validation, and iteration history metadata
- Pinned the metadata contract with tests for quick, standard, and deep runs plus degraded execution paths
- Clarified runtime naming and `--no-team` semantics to accurately reflect local execution versus distributed ambitions

#### Provider and Orchestration Hardening (6 tasks)

- Added tests for provider auth failure, timeout, rate-limit behavior, and empty but valid results with graceful fallback metadata
- Centralized retry and timeout behavior in orchestration with consistent telemetry recording
- Strengthened orchestrator failure-path tests covering sequential fallback, partial analysis, validation loops, and missing provider configuration

#### Content Generation Hardening (6 tasks)

- Defined explicit output contract expectations for each content-gen stage with versioned parsing assumptions
- Added golden fixtures for backlog, angle, research-pack, scripting, packaging, and QC stages covering both happy-path and malformed inputs
- Tightened fail-fast behavior so missing required fields on high-value stages cause clear errors rather than silent propagation

#### Content Gen Backlog Details Page (2 tasks)

- Added a dedicated backlog item details page at `/content-gen/backlog/<idea_id>` reachable from both grid cards and list rows
- Added shared backlog presentation helpers (timestamp formatting, badge variants) to avoid duplication across overview and detail views

#### Phase 01 - Superuser AI Triage Workspace (3 tasks)

- Added backend contracts and validation for batch AI triage proposals (POST /api/content-gen/backlog-ai/triage/respond, POST /api/content-gen/backlog-ai/triage/apply)
- Built the backlog-page triage workspace for reviewing and applying AI batch proposals with selective apply support
- Added batch analysis and enrichment behaviors including duplicate detection, clustering, gap analysis, and sparse item enrichment

#### Phase 02 - AI Decision Support And Execution Acceleration (3 tasks)

- Added next-action recommendations with rationale tied to backlog fields, scoring metadata, and proof gaps (POST /api/content-gen/backlog-ai/next-action, POST /api/content-gen/backlog-ai/next-action/batch)
- Added execution brief generation for production-readiness briefs grounded in backlog metadata (POST /api/content-gen/backlog-ai/execution-brief)
- Added superuser bulk actions with selectAll/deselectAll per group and per-item apply/reject outcomes

#### Backlog Chat Assistant (3 tasks)

- Added stateless chat workflow for backlog discussion with LLM-backed assistant that returns conversational replies plus structured proposals
- Added apply endpoint with validated operations through BacklogService (create_item, update_item, select_item, archive_item)
- Added frontend chat panel with proposal review cards and apply workflow wired to backend services

#### Content Gen Chat Page Upgrade (6 tasks)

- Added ChatWorkspace component with full workspace layout, page header, and backlog context insights
- Upgraded ChatThread with markdown rendering, localStorage transcript persistence, and slash commands (/edit, /propose)
- Added before/after field diff in proposal review with expand/collapse and operation-level dismissal
- Added session context and recovery with localStorage draft persistence across refreshes
- Added operator signals including starter prompts, insights derivation, and backlog health indicators

#### Backlog Single-Item Start (4 tasks)

- Added dedicated backend endpoint POST /api/content-gen/backlog/{idea_id}/start with 202 Accepted response
- Added seeded PipelineContext for single item with from_stage=4 (generate_angles) bypassing ideation and scoring
- Added Start Production action to backlog overview and detail pages with duplicate-run guard
- Added frontend workflow wiring with navigation to pipeline detail after start

#### Opportunity Planning Improvement (12 tasks)

Phase 01 - Stabilize contract and validation:
- Added structured output contract with JSON parsing mode and legacy fallback for opportunity planning stage
- Added semantic validation rules with BriefQualityWarning signals for audience specificity, problem observability, proof requirements, and duplicate sub-angles
- Added validate_opportunity_brief_quality() with coerce-and-validate approach and parse mode tracking in stage traces
- Reconciled OpportunityBrief fields with what the stage actually produces and stores

Phase 02 - Expand downstream consumption:
- Added backlog and scoring traceability linking generated and shortlisted ideas back to audience, problem, sub-angle, and proof constraints from the brief
- Added research hypothesis integration feeding opportunity-stage hypotheses into research-pack generation so evidence gathering tests planned claims
- Added success criteria integration in QC and post-publish evaluation flows so results are measured against original opportunity intent

Phase 03 - Close the learning loop:
- Added brief versus outcome analysis comparing original opportunity assumptions against downstream and post-publish results
- Added operator revision and versioning support for opportunity briefs with generated, edited, and approved version states
- Added learning store and planning metrics persisting reusable patterns and tracking brief pass rate, rewrite rate, and conversion to production

#### CI/CD and Dashboard Reliability (8 tasks)

- Added Python preflight CI workflow with lint, type check, and pytest subsets running on PRs and pushes
- Added dashboard CI workflow enforcing `npm run lint` and `npm run build` with mocked `@smoke` Playwright checks
- Stabilized dashboard smoke tests against mocked data for home, session, compare, and config surfaces
- Added WebSocket resilience tests verifying dashboard usability under connection failures, reconnects, and partial event streams
- Expanded mocked accessibility and contrast coverage across Research, Monitor, Compare, and Analytics surfaces with `npm run test:a11y` wired into CI and local preflight

#### Documentation and Release Hygiene (4 tasks)

- Removed drift between docs and CLI by aligning `README.md`, `docs/USAGE.md`, and `docs/README.md` with actual command registration and flags
- Extended release docs with complete repeatable validation flow including Python and dashboard checks, changelog, version bump, and tag steps
- Consolidated Python preflight, dashboard build, and essential smoke tests into one canonical `./scripts/preflight` command avoiding live API calls

### Removed

- Removed completed dashboard-upgrade planning documents `docs/tasks/01-dashboard-visual-foundation.md` through `docs/tasks/10-settings-runtime-clarity.md` after consolidating their delivered work into this changelog
- Removed previously completed task-planning documents from `docs/tasks/` after consolidating their delivered work into this changelog, including the dashboard-detail upgrade task pack
- Removed completed dashboard-upgrade planning documents `docs/tasks/11-search-cache-operations.md` through `docs/tasks/19-design-system-extraction-and-hardening.md` after consolidating their delivered work into this changelog
- Removed completed dashboard-upgrade planning documents `docs/tasks/20-trace-bundle-export-workspace.md` through `docs/tasks/29-dashboard-fixture-and-scenario-library.md` after consolidating their delivered work into this changelog
- Removed completed "necessary 80%" task-pack planning documents `docs/tasks/30_snapshot_session_metadata_contract.md` through `docs/tasks/47_add_canonical_necessary_80_preflight.md` and `docs/tasks/80_20_necessary_work_task_set.md` after consolidating their delivered work into this changelog
- Removed task-pack planning documents from `docs/tasks/` after consolidating their delivered work into this changelog, including decision graph observability, dashboard config editor, dashboard agent prompt editor, content generation expert workflow, backlog management, content-gen backlog details page, phase 01, phase 02, backlog chat assistant, content-gen chat page upgrade, backlog single-item start, and opportunity planning improvement task packs

## [0.1.0] - 2026-03-11

### Added

- Initial tracked release for the CC Deep Research CLI.
- Multi-stage research workflow with planning, source collection, analysis, validation, and reporting.
- Session persistence, telemetry ingestion, dashboard support, and a versioned benchmark corpus.

### Changed

- Established repository-level version tracking and a maintained changelog for future work history.
