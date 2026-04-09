# Task 41: Create a Dashboard CI Workflow

## Goal

Catch frontend regressions automatically.

## Scope

- add a GitHub Actions workflow for dashboard install, lint, build, and selected Playwright checks
- prefer mocked or fixture-backed E2E coverage
- keep the job fast enough for routine use

## Primary Files

- `.github/workflows/`
- `dashboard/package.json`
- `dashboard/tests/e2e/`

## Acceptance Criteria

- dashboard build is enforced in CI
- at least one smoke E2E path runs automatically

## Validation

- `cd dashboard && npm run build`
- `cd dashboard && npm run test:e2e -- --grep "app|config"`, or equivalent fast smoke subset

## Status

- [x] Done - added `dashboard-ci.yml`, enforced `npm run lint` and `npm run build`, and verified 2 mocked `@smoke` Playwright checks via `npm run test:e2e:smoke`
