# Dashboard Session Management Task Pack

This task pack breaks direct session management from the browser dashboard into small, dependency-ordered steps.

The target end state is:

- operators can delete session history directly from the dashboard
- deletion removes all session-backed artifacts consistently
- active sessions are protected from accidental destructive actions
- dashboard state updates immediately after a delete without stale rows or broken detail views

Phase 2 extends that baseline into broader lifecycle management so operators can search, stop, bulk-manage, archive, and reconcile session history without falling back to shell access.

Design constraints for this pack:

- keep destructive logic out of route handlers by introducing a small backend service
- treat session history as a multi-layer record: saved session JSON, telemetry files, and DuckDB analytics rows
- make delete behavior explicit and testable instead of relying on ad hoc filesystem cleanup
- start with single-session hard delete before considering bulk actions or archive semantics
- enrich list APIs enough that session-management UI does not need a detail fetch for basic decisions
- separate "stop active work" flows from "remove historical data" flows
- add reversible archive semantics before automated retention removes data permanently

## Task Order

1. [001_session_history_inventory.md](001_session_history_inventory.md)
2. [002_session_delete_contract.md](002_session_delete_contract.md)
3. [003_session_purge_service.md](003_session_purge_service.md)
4. [004_telemetry_and_duckdb_deletion_helpers.md](004_telemetry_and_duckdb_deletion_helpers.md)
5. [005_saved_session_artifact_deletion.md](005_saved_session_artifact_deletion.md)
6. [006_delete_session_api.md](006_delete_session_api.md)
7. [007_dashboard_client_delete_integration.md](007_dashboard_client_delete_integration.md)
8. [008_session_list_delete_action.md](008_session_list_delete_action.md)
9. [009_session_page_delete_flow.md](009_session_page_delete_flow.md)
10. [010_deletion_safety_and_validation.md](010_deletion_safety_and_validation.md)
11. [011_session_summary_enrichment.md](011_session_summary_enrichment.md)
12. [012_session_list_query_api.md](012_session_list_query_api.md)
13. [013_dashboard_session_list_filters.md](013_dashboard_session_list_filters.md)
14. [014_active_run_stop_api.md](014_active_run_stop_api.md)
15. [015_dashboard_active_run_stop_flow.md](015_dashboard_active_run_stop_flow.md)
16. [016_bulk_session_action_contract.md](016_bulk_session_action_contract.md)
17. [017_bulk_delete_service_and_api.md](017_bulk_delete_service_and_api.md)
18. [018_bulk_delete_dashboard_flow.md](018_bulk_delete_dashboard_flow.md)
19. [019_session_archive_and_restore.md](019_session_archive_and_restore.md)
20. [020_retention_reconciliation_and_audit.md](020_retention_reconciliation_and_audit.md)
