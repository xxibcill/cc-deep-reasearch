# P21-T3: Session Annotations and Triage

## Summary

Add session annotations, triage status, and handoff notes so review context stays attached to the run.

## Details

1. Define session-level fields for operator notes, triage status, owner, handoff target, and last reviewed timestamp.
2. Store annotations in `SessionStore` metadata or a focused sidecar store with migration-safe behavior.
3. Add dashboard UI on session overview and monitor pages.
4. Surface triage status in the session list and compare flows.
5. Include annotations in trace/debug exports where appropriate.
6. Add tests for create, update, clear, list display, and export behavior.

## Acceptance Criteria

- Operators can add, edit, and clear notes for a session.
- Sessions can be marked with triage states such as needs review, investigated, blocked, ready, or archived.
- Session list surfaces triage status without slowing the list path.
- Notes and status persist across dashboard reloads.
- Tests cover storage, API, and UI behavior.
