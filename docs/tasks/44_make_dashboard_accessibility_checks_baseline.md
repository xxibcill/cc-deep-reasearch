# Task 44: Make Accessibility Checks Part of the Dashboard Baseline

## Goal

Turn accessibility and contrast from occasional cleanup into routine regression protection.

## Scope

- ensure existing accessibility and contrast specs cover the main operator surfaces
- wire them into CI or a required local preflight command

## Primary Files

- `dashboard/tests/e2e/accessibility.spec.ts`
- `dashboard/tests/e2e/contrast.spec.ts`
- `dashboard/package.json`

## Acceptance Criteria

- a documented command exists for accessibility regression checks
- CI or preflight runs it consistently

## Validation

- `cd dashboard && npm run test:a11y`

## Status

- [x] Done - expanded mocked accessibility and contrast coverage across Research, Monitor, Compare, and Analytics; wired `npm run test:a11y` into dashboard CI plus local `scripts/preflight`; documented the baseline command in the dashboard README; and validated locally with `cd dashboard && npm run test:a11y`.
