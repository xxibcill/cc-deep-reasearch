# Task 020: Add Retention, Reconciliation, And Audit Tooling

Status: Planned

## Objective

Make session management operationally sustainable by adding background hygiene and operator-visible audit trails after stop, delete, archive, and restore flows exist.

## Scope

- add reconciliation tooling to detect drift between saved sessions, telemetry directories, and DuckDB rows
- define retention hooks for archived or deleted history so local storage can be cleaned intentionally over time
- record lightweight audit entries for stop, delete, archive, and restore actions
- document maintenance workflows, dry-run expectations, and recovery limits for operators

## Target Files

- `src/cc_deep_research/cli/session.py`
- `src/cc_deep_research/research_runs/`
- `src/cc_deep_research/telemetry/ingest.py`
- `docs/DASHBOARD_GUIDE.md`
- `docs/USAGE.md`

## Dependencies

- [017_bulk_delete_service_and_api.md](017_bulk_delete_service_and_api.md)
- [019_session_archive_and_restore.md](019_session_archive_and_restore.md)

## Acceptance Criteria

- operators can run a dry-run reconciliation pass to see storage drift before cleanup
- retention behavior is explicit and opt-in rather than silently removing history
- destructive and archival actions leave enough audit detail to explain what changed and when

## Suggested Verification

- run targeted `uv run pytest`
- verify any new maintenance commands expose `--help` and dry-run output
