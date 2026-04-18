# P7-T3 - Build Source Management, Empty States, And Dashboard Tests

## Status

Proposed.

## Summary

Add the UI needed to manage monitored sources and make sure Radar behaves truthfully in loading, empty, and error states.

## Scope

- Build source list and add-source flows.
- Add source health indicators.
- Add empty, loading, and error states for the main Radar routes.
- Add Playwright coverage for the critical dashboard flows.

## Out Of Scope

- Deep source-specific configuration editors
- Advanced collaboration or permissions

## Read These Files First

- `dashboard/tests/e2e/app.spec.ts`
- `dashboard/tests/e2e/dashboard-mocks.ts`
- `dashboard/src/components/ui/empty-state.tsx`
- `dashboard/src/components/config-editor.tsx`

## Suggested Files To Create Or Change

- `dashboard/src/components/radar/source-list.tsx`
- `dashboard/src/components/radar/source-form.tsx`
- `dashboard/src/app/radar/sources/page.tsx`
- `dashboard/tests/e2e/radar.spec.ts`
- `dashboard/tests/e2e/dashboard-mocks.ts`

## Implementation Guide

1. Build a simple source-management page that lists configured sources and shows health metadata.
2. Add the smallest add-source form that works for the initial source types. Do not overbuild complex per-source config on the first pass.
3. Add empty states for:
   - no sources configured
   - no scans run yet
   - no high-confidence opportunities found
4. Add loading and error states for both the inbox and source pages.
5. Add Playwright tests for:
   - viewing the Radar page
   - opening an opportunity detail
   - adding a source
   - seeing at least one empty-state scenario

## Guardrails For A Small Agent

- Do not fabricate activity in the empty state.
- Do not write brittle tests that depend on live backend data; use mocks or fixtures.
- Keep the source form minimal and aligned with the initial source set.

## Deliverables

- Source management UI
- Truthful empty/loading/error states
- Playwright coverage for main Radar flows

## Dependencies

- P7-T1 routing and API client
- P7-T2 inbox and detail UI

## Verification

- Run `cd dashboard && npm run lint`
- Run `cd dashboard && npm run test:e2e -- radar.spec.ts` if the local test setup supports file-scoped runs

## Acceptance Criteria

- Users can configure initial monitored sources from the dashboard.
- Radar has honest UI states when there is nothing to show.
- Basic end-to-end dashboard flows are covered by tests.
