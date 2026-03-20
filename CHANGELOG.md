# Changelog

All notable changes to this project will be documented in this file.
The format is based on Keep a Changelog, and this project follows Semantic Versioning.
History before `0.1.0` is summarized from the repository state captured on 2026-03-11.

## [Unreleased]

<!-- Add Added/Changed/Fixed entries here before cutting a release. -->

### Completed Task Packs

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

## [0.1.0] - 2026-03-11

### Added

- Initial tracked release for the CC Deep Research CLI.
- Multi-stage research workflow with planning, source collection, analysis, validation, and reporting.
- Session persistence, telemetry ingestion, dashboard support, and a versioned benchmark corpus.

### Changed

- Established repository-level version tracking and a maintained changelog for future work history.
