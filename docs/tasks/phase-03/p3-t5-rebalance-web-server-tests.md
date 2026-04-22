# P3-T5 - Rebalance Web Server Tests

## Outcome

`test_web_server.py` is split or reduced so route-domain behavior is easier to maintain.

## Scope

- Move research run tests to a research run route test module.
- Move session tests to session route test modules.
- Move search cache, benchmark, theme, and analytics tests to their domain modules.
- Keep app factory smoke tests in a small web server test file.

## Implementation Notes

- Preserve fixtures that create app instances.
- Avoid mixing route extraction with unrelated behavior changes.
- Keep test names descriptive during movement.

## Acceptance Criteria

- `test_web_server.py` is substantially smaller.
- Domain route tests are grouped by feature.
- The full backend test suite remains stable.

## Verification

- Run all backend tests or the moved test subset plus app smoke tests.
