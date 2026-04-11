# Task 03: Add Backlog Client And Store State

Status: Planned

Phase:
Phase 1 - Backlog Visibility

Goal:
Expose backlog loading and mutation primitives through the dashboard API client and Zustand store so the page can use one shared state path.

Primary files:
- `dashboard/src/lib/content-gen-api.ts`
- `dashboard/src/hooks/useContentGen.ts`

Scope:
- Add `listBacklog()` to the content-gen API client.
- Add typed placeholders for the later mutation helpers so store shape remains stable.
- Extend `useContentGen` with `backlog`, `backlogPath`, and `backlogLoading`.
- Add `loadBacklog()` and include it in `loadAll()` if that does not create unwanted overhead.
- Follow existing error handling patterns for dashboard API state.

Acceptance criteria:
- The dashboard has a shared state location for persistent backlog data.
- Backlog loading can happen independently of pipeline selection.
- Errors and loading states follow existing content-studio conventions.

Validation:
- Manual store exercise from a page or component that calls `loadBacklog()`.

Out of scope:
- The dedicated backlog route UI
- Real mutation behavior beyond state shape
- Backend create support
