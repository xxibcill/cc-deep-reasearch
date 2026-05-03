# P18-T3: Split Session Detail Loading

## Summary

Reduce monitor startup cost by loading only the data needed for the first screen, then fetching heavy detail sections on demand.

## Details

1. Split the current `GET /api/sessions/{session_id}` monitor payload into lightweight pieces:
   - session summary
   - first or latest event page
   - prompt metadata
   - derived outputs
   - checkpoint inventory
2. Keep backward compatibility for callers that still request the existing combined payload during migration.
3. Update `dashboard/src/components/session-telemetry-workspace.tsx` so monitor startup does not wait for derived outputs and checkpoint metadata before showing event history.
4. Avoid duplicate initial history loading from both HTTP detail fetch and WebSocket history refresh.
5. Fetch derived outputs lazily when the user opens derived, decision graph, or graph-heavy views.
6. Keep historical sessions usable when the websocket is disabled.

## Acceptance Criteria

- The monitor can render session status and initial events without derived outputs being present.
- WebSocket history and HTTP event-page loading do not append the same initial events twice.
- Derived outputs still render correctly when their dependent views are opened.
- Checkpoint, report, and trace bundle workflows still work.
- Tests cover active session, historical session, and missing derived-output paths.
