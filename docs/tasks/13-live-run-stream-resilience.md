# Task 13: Harden Live Run Streaming And Reconnection Behavior

Status: Done

## Goal

Make live session monitoring resilient when WebSocket connections are interrupted, delayed, or partially stale.

## Depends On

- Tasks 01 through 12 complete

## Primary Areas

- `dashboard/src/lib/websocket.ts`
- `dashboard/src/components/session-telemetry-workspace.tsx`
- `dashboard/src/hooks/useDashboard.ts`
- `dashboard/src/components/run-status-summary.tsx`
- `dashboard/src/components/telemetry/telemetry-header.tsx`

## Problem To Solve

The monitor depends on live updates, but operators need more confidence when the stream is unstable:

- reconnection state may be too implicit
- a broken socket can look like a dead run
- stale buffered events versus live events may not be clearly distinguished

## Required Changes

1. Improve reconnection handling and visible connection states.
2. Distinguish clearly between:
   - connected live stream
   - reconnecting
   - historical-only data
   - failed live connection
3. Ensure event buffering and deduplication remain safe during reconnect.
4. Give the operator clear recovery actions when the stream cannot resume.

## Implementation Guidance

- Preserve existing session-detail fetch plus WebSocket merge behavior.
- Avoid aggressive polling unless required as a fallback.
- If reconnect backoff exists, make it visible in the UI enough to explain what is happening.
- Keep the monitor useful even when live streaming fails.

## Out Of Scope

- backend WebSocket protocol redesign
- cross-tab stream coordination
- browser push notifications

## Acceptance Criteria

- Live monitoring is more trustworthy under transient connection failures.
- Operators can tell whether a run is quiet, stalled, historical, or disconnected.
- No duplicate-event regressions are introduced during reconnect.

## Verification

- Simulate socket interruption and reconnection.
- Confirm event lists remain de-duplicated and ordered.
- Check status messaging for historical sessions with no active stream.
