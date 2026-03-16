# Task 015: Add A Combined Dashboard Dev Launcher

Status: Planned

## Objective

Create a single development launcher that starts the backend API and Next.js frontend together.

## Scope

- add a Node-based launcher script for process management
- start the backend on port `8000`
- start Next.js on port `3000`
- propagate exit signals so one `Ctrl+C` stops both processes

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/scripts/dev.mjs`

## Dependencies

- none

## Acceptance Criteria

- one launcher script starts both required local processes
- process shutdown is clean and predictable
- logs are labeled clearly enough to distinguish frontend from backend output

## Suggested Verification

- run `node /Users/jjae/Documents/guthib/cc-deep-research/dashboard/scripts/dev.mjs`

