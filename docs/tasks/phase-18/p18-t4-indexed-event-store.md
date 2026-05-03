# P18-T4: Indexed Event Store

## Summary

Replace repeated full-array event de-duplication and sorting with indexed event state that supports fast websocket appends and paginated history.

## Details

1. Refactor dashboard event state in `dashboard/src/hooks/useDashboard.ts` to track events by `eventId` and maintain ordered sequence metadata.
2. Preserve the existing public selector behavior so components can still read ordered `events`.
3. Make `appendEvent`, `appendEvents`, and `appendBufferedEvents` avoid repeated `Array.some()`, full `Map` rebuilds, and full sorts for already-ordered websocket batches.
4. Preserve `MAX_BUFFERED_EVENTS` behavior for live buffers while allowing historical pagination to load older pages intentionally.
5. Ensure selected event references remain valid when the event buffer is pruned.
6. Add unit tests for duplicate events, out-of-order batches, buffer pruning, reloads, and selected-event retention.

## Acceptance Criteria

- WebSocket event appends are O(batch size) for the common ordered case.
- Duplicate event IDs are ignored without scanning the full event array.
- The monitor renders events in the same order as before.
- Live buffer pruning still caps memory growth.
- Existing components do not need broad rewrites to consume event state.
