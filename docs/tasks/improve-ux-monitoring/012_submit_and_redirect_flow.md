# Task 012: Add Submit And Redirect Flow

Status: Complete

## Objective

Wire the launch form to the new backend API and move the user directly into the session view after submission.

## Scope

- call the start-run API on submit
- show pending and error states
- redirect to the session page using the returned session id
- preserve enough local run state for polling after navigation

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/app/page.tsx`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/components/start-research-form.tsx`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/hooks/useDashboard.ts`

## Dependencies

- [011_home_page_research_form.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/011_home_page_research_form.md)

## Acceptance Criteria

- submitting a query starts a run and routes the user into the live session screen
- the UI exposes errors without leaving the page in an ambiguous state
- duplicate submits are blocked while a request is in flight

## Suggested Verification

- run `npm run build` in `/Users/jjae/Documents/guthib/cc-deep-research/dashboard`

