# Phase 4: Hardening And Rollout

Status: Planned

Functional feature:
Backlog management is integrated cleanly into the content studio navigation and protected by backend and frontend tests.

Why this phase exists:
- The current content studio mixes query-string tabs with redirect-only subroutes.
- CRUD work will be fragile without direct route coverage and dashboard test coverage.
- This phase turns a working feature into a maintainable one.

Tasks in this phase:
1. `10-content-studio-navigation-and-route-cleanup.md`
2. `11-backlog-api-tests.md`
3. `12-backlog-management-frontend-tests.md`

Exit criteria:
- Navigation makes backlog management discoverable and coherent.
- Backend route tests cover list, create, update, select, archive, and delete behavior.
- Frontend tests cover the main backlog management flows.
