# Task 04: Redesign The Session Overview Panel

## Goal

Replace the current static-details page with a stronger session overview that belongs inside the unified workspace and acts as the operator’s first stop.

## Depends On

- Tasks 01 through 03 complete

## Primary Areas

- `dashboard/src/components/session-static-details.tsx`
- `dashboard/src/app/session/[id]/page.tsx`
- `dashboard/src/components/session-page-frame.tsx`
- `dashboard/src/lib/session-route.ts`
- `dashboard/src/types/telemetry.ts` only if small UI-facing helpers are needed

## Problem To Solve

The current overview is mostly a fact sheet:

- it repeats raw metadata
- it does not guide the operator toward the next useful action
- it looks visually older than the rest of the workspace

## Required Changes

1. Recast the overview as an operator summary, not a metadata dump.
2. The page should quickly answer:
   - what this session is about
   - whether it succeeded, failed, or is still active
   - how much evidence and activity it generated
   - whether report and payload artifacts exist
   - what the operator should do next
3. Keep detailed session facts available, but demote them below the primary summary.
4. Add stronger next-step affordances:
   - inspect live telemetry
   - open the report if available
   - return to the home control room if the run is inactive

## Implementation Guidance

- Avoid just restyling the existing metric cards.
- Group content into summary, execution snapshot, artifacts, and technical facts.
- If the query is long, display it in a readable, non-overwhelming format.
- Do not repeat the same status badge or counts in three different places.
- Use the new shell from Task 03 rather than fighting it.

## Out Of Scope

- telemetry visualizations
- report rendering changes
- compare flow changes

## Acceptance Criteria

- The overview feels like a meaningful summary page, not a property list.
- Important artifacts and next actions are obvious.
- Technical facts remain available without dominating the page.
- The surface matches the session shell and home page styling.

## Verification

- Test overview for:
  - active session
  - completed session with report
  - completed session without report
  - archived session
- Check long query handling and narrow screen behavior.
