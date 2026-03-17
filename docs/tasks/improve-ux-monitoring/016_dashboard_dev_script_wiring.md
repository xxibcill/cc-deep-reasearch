# Task 016: Wire `npm run dev` To The Combined Launcher

Status: Complete

## Objective

Make `npm run dev` inside `dashboard/` use the new combined launcher by default.

## Scope

- update package scripts to call the launcher
- keep a direct Next.js-only script available for debugging if useful
- document any environment assumptions needed by the launcher

## Target Files

- `dashboard/package.json`
- `dashboard/README.md`

## Dependencies

- [015_dashboard_dev_launcher_script.md](015_dashboard_dev_launcher_script.md)

## Acceptance Criteria

- `npm run dev` starts both the frontend and backend
- the script behavior matches the documented ports
- there is still an obvious escape hatch for frontend-only debugging if needed

## Suggested Verification

- run `npm run dev` in `dashboard`

