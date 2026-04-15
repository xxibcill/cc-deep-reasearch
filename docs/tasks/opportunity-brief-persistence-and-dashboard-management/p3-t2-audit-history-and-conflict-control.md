# Task P3-T2: Audit History And Conflict Control

## Objective

Add revision history, audit visibility, and conflict control so multiple operators or long-lived sessions do not corrupt brief state.

## Scope

- Record who created, edited, approved, archived, or cloned a brief.
- Add optimistic concurrency or equivalent edit conflict detection.
- Expose audit and history endpoints suitable for dashboard inspection.
- Define conflict behavior for approval actions and AI apply actions.

## Acceptance Criteria

- Operators can inspect how and why a brief changed over time.
- Concurrent edits do not silently overwrite each other.
- Approval events and revision changes are traceable without reading raw storage files.

## Advice For The Smaller Coding Agent

- Use a simple explicit concurrency mechanism such as revision id or updated-at preconditions.
- Keep audit events readable by operators, not only by developers.
