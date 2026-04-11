# Task 04: Create Dedicated Backlog Page Shell

Status: Planned

Phase:
Phase 1 - Backlog Visibility

Goal:
Add a real `/content-gen/backlog` route that renders inside the content-studio shell and loads the persistent backlog on mount.

Primary files:
- `dashboard/src/app/content-gen/backlog/page.tsx`
- `dashboard/src/components/content-gen/content-gen-shell.tsx`

Scope:
- Add the new route file for `/content-gen/backlog`.
- Reuse the content studio shell and existing layout conventions.
- Load persistent backlog state from the shared store.
- Show loading, empty, and error states for the route.
- Keep the page narrow enough to support later create and edit controls without redesign.

Acceptance criteria:
- Operators can navigate directly to `/content-gen/backlog`.
- The route renders within the existing content-studio chrome.
- The page does not depend on a selected pipeline to show backlog data.

Validation:
- Manual browser verification of route load and state transitions.

Out of scope:
- Advanced table behavior
- Mutation wiring
- Navigation cleanup beyond what is needed to reach the page directly
