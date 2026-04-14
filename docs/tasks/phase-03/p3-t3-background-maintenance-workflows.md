# Task P3-T3: Background Maintenance Workflows

## Objective

Use AI for repeatable backlog maintenance jobs while keeping destructive changes behind explicit operator review.

## Scope

- Add recurring AI maintenance workflows for:
  - stale item review
  - gap summaries
  - duplicate watchlists
  - optional rescoring recommendations
- Surface results as inbox-style review items or proposal queues.
- Ensure background workflows do not silently mutate backlog state.

## Acceptance Criteria

- The system can generate repeatable backlog-health outputs without manual prompting.
- Maintenance outputs are reviewable and actionable by a superuser.
- Background AI jobs improve backlog hygiene without bypassing governance controls.

## Advice For The Smaller Coding Agent

- Keep the first maintenance jobs read-mostly.
- Reuse proposal-review patterns instead of inventing a second approval system.
- Design outputs around operator actionability, not raw model verbosity.
