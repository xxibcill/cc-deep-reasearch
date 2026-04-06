# Task 09: Refresh Tests, Screenshots, And Dashboard Documentation

## Goal

Bring tests, visual baselines, and docs back into sync with the upgraded dashboard.

## Depends On

- Tasks 01 through 08 complete

## Primary Areas

- `dashboard/tests/e2e/app.spec.ts`
- `dashboard/tests/e2e/accessibility.spec.ts`
- any other affected Playwright specs under `dashboard/tests/e2e/`
- `dashboard/playwright-screenshots/`
- `docs/DASHBOARD_GUIDE.md`
- optional additional dashboard docs if the route model or major UI behavior changed

## Problem To Solve

The checked-in screenshots and some test coverage are minimal and no longer capture the real dashboard structure. After the upgrade work, docs and tests need to describe the new operator workflow accurately.

## Required Changes

1. Expand Playwright coverage beyond “page loads”:
   - home page control-room structure
   - session workspace navigation
   - compare flow
   - key empty/error states where practical
2. Update accessibility checks if selectors or structure changed.
3. Refresh or replace screenshot artifacts under `dashboard/playwright-screenshots/` so they reflect the new UI.
4. Update `docs/DASHBOARD_GUIDE.md` to match:
   - home-page structure
   - session workspace model
   - compare and triage behavior if changed materially

## Implementation Guidance

- Keep tests resilient to layout changes by selecting semantic text, roles, and stable labels where possible.
- If some screenshot artifacts are obsolete, replace them rather than leaving misleading references around.
- Update docs after the implementation settles, not before.

## Out Of Scope

- major product redesign
- backend API documentation unrelated to dashboard changes

## Acceptance Criteria

- Dashboard tests cover the new primary flows at a meaningful level.
- Screenshot artifacts no longer show outdated layouts.
- `docs/DASHBOARD_GUIDE.md` accurately describes the shipped UI.

## Verification

- Run the updated Playwright test set.
- Manually inspect refreshed screenshots.
- Read the dashboard guide once after editing to ensure it matches the implemented routes and page structure.
