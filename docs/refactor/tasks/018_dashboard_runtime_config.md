# Task 018: Dashboard Runtime Config

Status: Done

## Objective

Remove hardcoded API and WebSocket endpoints from the dashboard and replace them with runtime-configurable settings.

## Scope

- extract API base URL and WebSocket base URL into one configuration source
- keep the current local-development defaults
- avoid changing page structure in this task

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/lib/api.ts`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/lib/websocket.ts`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/README.md`

## Dependencies

- [002_clean_generated_artifacts.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/002_clean_generated_artifacts.md)

## Acceptance Criteria

- dashboard networking config is centralized
- local defaults still work
- developers can point the dashboard at non-default backend hosts without code edits

## Suggested Verification

- run `npm run build` in `/Users/jjae/Documents/guthib/cc-deep-research/dashboard`
