# Phase 1: Backlog Visibility

Status: Planned

Functional feature:
Operators can open a dedicated backlog management page and see the persistent backlog with stable metadata and useful filtering.

Why this phase exists:
- The repo already has persistent backlog storage and list APIs.
- The current backlog tab in `/content-gen` is pipeline-scoped and uses no-op action handlers.
- Before adding deeper CRUD flows, the team needs one reliable operator surface for the managed backlog.

Tasks in this phase:
1. `01-persistent-backlog-source-of-truth.md`
2. `02-backlog-api-contract-and-dashboard-types.md`
3. `03-backlog-client-and-store-state.md`
4. `04-dedicated-backlog-page-shell.md`
5. `05-backlog-list-and-filter-experience.md`

Exit criteria:
- `/content-gen/backlog` renders through the content studio shell.
- The page loads data from `GET /api/content-gen/backlog`.
- Backlog metadata is not silently dropped by stale dashboard types.
- Operators can inspect the persistent backlog without selecting a pipeline first.
