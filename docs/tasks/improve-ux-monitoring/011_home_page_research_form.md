# Task 011: Add Research Start Form To The Home Page

Status: Planned

## Objective

Make the home page a launch surface, not only a session browser.

## Scope

- add a dedicated start-research form component
- support the minimum useful launch fields:
  - query
  - depth
  - optional output preferences only if they matter to the browser UX
- keep the existing recent sessions view visible

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/app/page.tsx`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/components/start-research-form.tsx`

## Dependencies

- [010_dashboard_client_run_api_integration.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/010_dashboard_client_run_api_integration.md)

## Acceptance Criteria

- the home page has an obvious place to submit a new research query
- the launch form is separate from the session list component
- the page still works when there are no historical sessions yet

## Suggested Verification

- run `npm run build` in `/Users/jjae/Documents/guthib/cc-deep-research/dashboard`

