# P4-T5 - Sync Dashboard Type Fixtures

## Outcome

Dashboard TypeScript expectations align with backend contract fixtures.

## Scope

- Align dashboard content-gen fixtures with backend JSON fixtures.
- Add or update tests that parse representative backend payloads.
- Confirm TypeScript types match backend contracts.
- Keep Playwright mocks aligned with backend responses.

## Implementation Notes

- Use shared JSON fixtures where practical.
- Keep dashboard mocks realistic enough to catch contract drift.
- Avoid frontend behavior changes in this task.

## Acceptance Criteria

- Dashboard fixture payloads match backend contract tests.
- TypeScript checks catch incompatible payload assumptions.
- Playwright mocks remain in sync with backend routes.

## Verification

- Run dashboard type/build checks and relevant e2e tests.
