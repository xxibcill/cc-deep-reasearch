# Task 049: Integrate shadcn/ui Into The Dashboard

Status: Planned

## Objective

Adopt `shadcn/ui` primitives in the Next.js dashboard so complex inspection views use a more consistent and accessible component foundation before deeper UI expansion lands.

## Scope

- add the minimum `shadcn/ui` setup needed for the existing dashboard stack
- replace custom modal, badge, and table primitives where shared components improve consistency
- introduce reusable UI building blocks for dialog, tabs, select, badge, and scrollable panes
- keep the existing visual language and routing intact while reducing hand-rolled component duplication
- avoid broad redesign work that is unrelated to dashboard inspection flows

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/package.json`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/app/globals.css`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/components/session-details.tsx`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/components/ui/`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/README.md`

## Dependencies

- [034_operator_dashboard_live_console.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/034_operator_dashboard_live_console.md)

## Acceptance Criteria

- the dashboard includes a documented `shadcn/ui` setup that works with the existing Next.js and Tailwind stack
- at least the current dialog, badge, and table-like interaction surfaces use shared UI primitives instead of bespoke markup
- the session detail page remains functional with no regression in keyboard access or live-event interaction
- the component layer is ready to be reused by later graph, timeline, tool, and LLM detail work

## Exit Criteria

- contributors can add new dashboard panels using shared primitives rather than rebuilding common UI patterns each time
- the dashboard has a clearer base component vocabulary for later enhancements

## Suggested Verification

- run `npm run lint` in `dashboard/`
- manually verify keyboard navigation, dialog open-close behavior, and responsive layout on the session page
