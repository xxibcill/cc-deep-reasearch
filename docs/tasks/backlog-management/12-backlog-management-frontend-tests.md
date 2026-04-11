# Task 12: Add Backlog Management Frontend Tests

Status: Planned

Phase:
Phase 4 - Hardening And Rollout

Goal:
Cover the main backlog-management operator flows in the dashboard test suite.

Primary files:
- `dashboard/tests/e2e/content-gen.spec.ts`
- new: `dashboard/tests/e2e/backlog-management.spec.ts`
- `dashboard/tests/e2e/dashboard-mocks.ts`

Scope:
- Add route coverage for the dedicated backlog page.
- Test list rendering and empty state behavior.
- Test at least one successful update flow and one failure flow.
- Test create flow once backend support is available.
- Keep the test setup aligned with current dashboard mock patterns.

Acceptance criteria:
- Frontend tests cover the main backlog-management flows that operators rely on.
- CRUD regressions in the dashboard surface in automated test runs.
- The tests do not depend on a selected pipeline to exercise backlog management.

Validation:
- Run the relevant dashboard Playwright test targets.

Out of scope:
- Exhaustive visual snapshot coverage
- Cross-browser matrix expansion
