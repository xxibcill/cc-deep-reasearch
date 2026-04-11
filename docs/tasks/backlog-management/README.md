# Backlog Management Task Pack

Status: Planned

This folder breaks the backlog-management feature into phased, functional increments for the content generation workflow.

Working rules:
- Keep scope narrow. Do only the task you were assigned.
- Reuse the existing persistent backlog path powered by `BacklogService`.
- Prefer additive changes over routing rewrites unless the task explicitly covers navigation cleanup.
- Keep dashboard types aligned with Python models before expanding UI behavior.
- Add or update tests for the files you touch when the task explicitly asks for it.

Recommended order:
1. `phase-01-backlog-visibility.md` - Planned
2. `01-persistent-backlog-source-of-truth.md` - Planned
3. `02-backlog-api-contract-and-dashboard-types.md` - Planned
4. `03-backlog-client-and-store-state.md` - Planned
5. `04-dedicated-backlog-page-shell.md` - Planned
6. `05-backlog-list-and-filter-experience.md` - Planned
7. `phase-02-existing-item-management.md` - Planned
8. `06-wire-existing-item-actions.md` - Planned
9. `07-edit-existing-backlog-items.md` - Planned
10. `phase-03-full-crud-create-flow.md` - Planned
11. `08-backlog-create-endpoint-and-service-support.md` - Planned
12. `09-create-backlog-item-ui-flow.md` - Planned
13. `phase-04-hardening-and-rollout.md` - Planned
14. `10-content-studio-navigation-and-route-cleanup.md` - Planned
15. `11-backlog-api-tests.md` - Planned
16. `12-backlog-management-frontend-tests.md` - Planned

Phase summary:
- Phase 1: Operators can open a dedicated backlog page and reliably see the persistent backlog with filters.
- Phase 2: Operators can manage existing backlog items with update, select, archive, and delete flows.
- Phase 3: Operators can create new backlog items, completing CRUD support.
- Phase 4: The experience is integrated into studio navigation and covered by backend and frontend tests.

Parallelization guidance:
- Tasks 01 and 02 should stay sequential because the API contract depends on the chosen source of truth.
- Tasks 03 and 04 can overlap once the API shape is fixed if one owner handles state and another handles page layout.
- Task 05 should land after tasks 03 and 04 because it depends on both store state and the dedicated page shell.
- Tasks 06 and 07 are sequential because edit UX depends on real mutation wiring.
- Tasks 08 and 09 are sequential because UI create flow needs backend create support first.
- Tasks 10, 11, and 12 can proceed in parallel after the main CRUD flow is stable.

Definition of done for the feature pack:
- `/content-gen/backlog` exists as a real operator-facing page.
- The page reads from the persistent managed backlog, not the currently selected pipeline context.
- Operators can create, edit, select, archive, and delete backlog items.
- Dashboard types stay aligned with `src/cc_deep_research/content_gen/models.py`.
- The main API and dashboard flows are covered by tests.
