# Task 019: Dashboard State And Components

Status: Done

## Objective

Split dashboard state and page rendering into smaller typed units so the frontend can evolve without page-level sprawl.

## Scope

- remove duplicated session and event state between local page state and shared store
- extract reusable page sections and event-table components
- replace `any` usage with local typed shapes

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/app/page.tsx`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/app/session/[id]/page.tsx`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/hooks/useDashboard.ts`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/types/telemetry.ts`

## Dependencies

- [018_dashboard_runtime_config.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/018_dashboard_runtime_config.md)

## Acceptance Criteria

- dashboard pages delegate to smaller components and typed state helpers
- session lists and event streams stop duplicating the same state ownership
- the UI behavior remains unchanged apart from internal cleanup

## Suggested Verification

- run `npm run build` in `/Users/jjae/Documents/guthib/cc-deep-research/dashboard`
