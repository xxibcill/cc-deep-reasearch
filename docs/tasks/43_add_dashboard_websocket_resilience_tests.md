# Task 43: Add WebSocket Resilience Tests for the Dashboard

**Status: Done**

## Goal

Verify that realtime behavior degrades safely under reconnects, dropped events, or backend absence.

## Scope

- test initial connection failure
- test reconnect handling
- test partial event streams
- assert the UI stays usable when live updates are unavailable

## Primary Files

- `dashboard/src/lib/websocket.ts`
- `dashboard/src/hooks/`
- `dashboard/tests/e2e/`

## Acceptance Criteria

- the dashboard remains operable during websocket failure states
- failure UI is explicit and non-blocking

## Validation

- `cd dashboard && npm run test:e2e -- --grep "realtime|content-gen|observability"`
