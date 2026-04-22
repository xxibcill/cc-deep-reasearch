# P4-T2 - Add Storage Migration Contract Tests

## Outcome

Storage migration and legacy field normalization behavior is tested at storage boundaries.

## Scope

- Test YAML-to-SQLite migration where supported.
- Test legacy backlog field normalization.
- Test legacy brief conversion.
- Test missing or partial persisted data recovery.

## Implementation Notes

- Use temporary directories and local stores.
- Avoid depending on user config directories.
- Keep migration fixtures small and explicit.

## Acceptance Criteria

- Persisted legacy records load into current models.
- Migration tests do not require external services.
- Backward compatibility behavior is documented by tests.

## Verification

- Run storage and content-gen model tests.
