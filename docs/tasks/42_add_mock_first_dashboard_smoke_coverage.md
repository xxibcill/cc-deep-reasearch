# Task 42: Add Mock-First Dashboard Smoke Coverage

## Goal

Make UI regression testing reliable without needing live backend state.

## Scope

- identify the minimum mocked flows for home, session, compare, and config surfaces
- stabilize fixtures and test helpers
- reduce dependence on timing-sensitive live websocket behavior in basic smoke tests

## Primary Files

- `dashboard/tests/e2e/dashboard-mocks.ts`
- `dashboard/tests/e2e/app.spec.ts`
- `dashboard/tests/e2e/config-editor.spec.ts`
- `dashboard/tests/e2e/`

## Acceptance Criteria

- fast smoke tests can run entirely from mocked data
- core pages render and basic interactions work

## Validation

- `cd dashboard && npm run test:e2e -- --grep "app|config|compare"`

## Status

- [x] Done - 63 tests passing (3 skipped, 6 pre-existing failures unrelated to scope)
