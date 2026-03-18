# Dashboard Session Management Task Pack

This task pack breaks direct session management from the browser dashboard into small, dependency-ordered steps.

The target end state is:

- operators can delete session history directly from the dashboard
- deletion removes all session-backed artifacts consistently
- active sessions are protected from accidental destructive actions
- dashboard state updates immediately after a delete without stale rows or broken detail views

Design constraints for this pack:

- keep destructive logic out of route handlers by introducing a small backend service
- treat session history as a multi-layer record: saved session JSON, telemetry files, and DuckDB analytics rows
- make delete behavior explicit and testable instead of relying on ad hoc filesystem cleanup
- start with single-session hard delete before considering bulk actions or archive semantics

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
