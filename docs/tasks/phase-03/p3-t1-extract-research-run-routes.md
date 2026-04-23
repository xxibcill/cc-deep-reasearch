# P3-T1 - Extract Research Run Routes

## Outcome

Research run HTTP routes live in a focused route module.

## Scope

- Move start, status, and stop routes out of `web_server.py`.
- Preserve `ResearchRunService` usage.
- Preserve job registry and cancellation behavior.
- Keep API paths unchanged.

## Implementation Notes

- Pass runtime dependencies from `create_app()` or a small dependency accessor.
- Avoid duplicating app state logic.
- Keep route tests pointed at the same public paths.

## Acceptance Criteria

- `web_server.py` no longer contains research run route bodies.
- Existing research run API tests pass.
- Route paths and response payloads are unchanged.

## Verification

- Run research run service and route tests.
