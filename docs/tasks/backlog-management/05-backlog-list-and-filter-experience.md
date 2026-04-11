# Task 05: Deliver Read-Only Backlog List And Filters

Status: Planned

Phase:
Phase 1 - Backlog Visibility

Goal:
Use the existing backlog panel as the backbone for a real backlog-management list view with persistent data and useful filtering.

Primary files:
- `dashboard/src/components/content-gen/backlog-panel.tsx`
- `dashboard/src/app/content-gen/backlog/page.tsx`

Scope:
- Render persistent backlog items through `BacklogPanel`.
- Preserve existing status and category filtering behavior.
- Show backlog path metadata on the page.
- Ensure the table handles the fuller backlog type shape without layout breaks.
- Keep action controls visually present but only wire the behaviors in later tasks.

Acceptance criteria:
- Operators can inspect persistent backlog items from the dedicated page.
- Filter controls work against persistent backlog data.
- The page presents a useful empty state when no items exist.

Validation:
- Manual list review with seeded backlog data.

Out of scope:
- Real mutations
- Edit dialogs
- Create flow
