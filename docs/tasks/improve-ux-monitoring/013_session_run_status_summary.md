# Task 013: Add Session Run Status Summary

Status: Complete

## Objective

Make the session page explain run state clearly instead of showing only raw event counts and websocket status.

## Scope

- poll run status alongside websocket events
- show queued, running, completed, and failed states
- surface query, depth, and major progress facts in the header or summary block

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/app/session/[id]/page.tsx`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/components/session-details.tsx`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/hooks/useDashboard.ts`

## Dependencies

- [008_research_run_status_api.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/008_research_run_status_api.md)
- [012_submit_and_redirect_flow.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/012_submit_and_redirect_flow.md)

## Acceptance Criteria

- the session page explains whether the run is still active or already finished
- users can tell the difference between websocket disconnects and run completion
- the status summary is usable even before enough events exist for a meaningful table

## Suggested Verification

- run `npm run build` in `/Users/jjae/Documents/guthib/cc-deep-research/dashboard`

