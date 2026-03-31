# 12. Dashboard shadcn Testing And Rollout

Status: Done

## Goal

Land the shadcn migration safely by adding verification, sequencing, and cleanup work after the UI refactors are complete.

## Scope

- regression checks
- accessibility review
- visual consistency review
- dead-code cleanup
- documentation updates

## Non-Goals

- Building a full Storybook in this task
- Blocking rollout on exhaustive visual snapshot coverage

## Work

- Audit for remaining raw `input`, `textarea`, `select`, `table`, and ad hoc dialog markup in app components
- Update dashboard docs to describe the expanded shared `ui/` surface
- Run and, where needed, extend:
  - Playwright dashboard tests
  - accessibility checks
  - contrast checks
- Remove dead styles and dead helper code left behind by migrated components
- Capture any intentionally custom surfaces that should not be forced into shadcn

## Acceptance Criteria

- The migration leaves a clearly smaller set of one-off controls in app components
- Existing dashboard tests still pass, or missing coverage is explicitly documented
- The repo docs reflect the new primitive layer and migration boundaries

## Likely Files

- `dashboard/tests/e2e/*.spec.ts`
- `dashboard/src/components/**/*`
- `dashboard/src/app/**/*`
- `dashboard/README.md`
- `docs/DASHBOARD_GUIDE.md`
- `DESIGN_SYSTEM_EXTRACTION_PLAN.md`

## Depends On

- All prior dashboard shadcn task files
