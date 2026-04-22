# P5-T4 - Add Focused Frontend Store Tests

## Outcome

Frontend state behavior is covered without relying only on Playwright workflows.

## Scope

- Add tests for feature store reducers/actions.
- Add tests for API error handling.
- Add tests for merge/update behavior where state is nontrivial.
- Keep e2e tests for user workflows.

## Implementation Notes

- Use the dashboard's existing test tooling if available.
- Prefer fast unit-level tests for state transitions.
- Keep mocks close to API contract fixtures.

## Acceptance Criteria

- Store behavior regressions fail fast.
- Playwright tests do not need to cover every state branch.
- Error states are covered for key mutations.

## Verification

- Run frontend test suite and targeted e2e tests.
