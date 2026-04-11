# Phase 3: Full CRUD Create Flow

Status: Done

Functional feature:
Operators can create backlog items from the dashboard, completing CRUD support for backlog management.

Why this phase exists:
- The current backend does not expose backlog item creation.
- A new backlog page without create support still leaves operators dependent on generated items or manual file edits.
- This phase closes the main product gap between "manage backlog" and true CRUD.

Tasks in this phase:
1. `08-backlog-create-endpoint-and-service-support.md`
2. `09-create-backlog-item-ui-flow.md`

Exit criteria:
- The backend supports a typed create endpoint for backlog items.
- The dashboard exposes a new-item flow with validation.
- Newly created items persist to the managed backlog file and appear on reload.
