# Task 06: Wire Existing Item Actions

Status: Planned

Phase:
Phase 2 - Existing Item Management

Goal:
Connect the existing non-create backlog actions to real backend endpoints and shared dashboard state.

Primary files:
- `src/cc_deep_research/content_gen/router.py`
- `dashboard/src/lib/content-gen-api.ts`
- `dashboard/src/hooks/useContentGen.ts`
- `dashboard/src/components/content-gen/backlog-panel.tsx`

Scope:
- Add client helpers for `PATCH`, `select`, `archive`, and `delete`.
- Add store actions that call those helpers and refresh or update local backlog state.
- Replace no-op backlog handlers in the dashboard with real actions.
- Keep action-level error handling local enough that one failed mutation does not blank the page.

Acceptance criteria:
- Status updates call the real patch endpoint.
- Select, archive, and delete buttons change persistent backlog state.
- The page reflects mutations without requiring a manual reload.

Validation:
- Manual mutation pass against a seeded backlog file.

Out of scope:
- Full metadata editing
- Item creation
- Test coverage
