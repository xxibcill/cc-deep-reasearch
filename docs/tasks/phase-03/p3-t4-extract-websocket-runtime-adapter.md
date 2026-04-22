# P3-T4 - Extract WebSocket Runtime Adapter

## Outcome

WebSocket connection handling is separated from app setup while preserving live event behavior.

## Scope

- Move session WebSocket route behavior into a focused module.
- Preserve `EventRouter` and `WebSocketConnection` behavior.
- Preserve debug logging and disconnect handling.
- Keep WebSocket paths unchanged.

## Implementation Notes

- Keep `DashboardBackendRuntime` lifecycle in app composition.
- Avoid changing client reconnect semantics.
- Add tests or e2e coverage for reconnect behavior if touched.

## Acceptance Criteria

- WebSocket route implementation is not embedded in `web_server.py`.
- Existing WebSocket resilience tests pass.
- Live dashboard event streaming remains compatible.

## Verification

- Run WebSocket backend tests and dashboard WebSocket e2e tests.
