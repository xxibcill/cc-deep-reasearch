# Task 045: Build The D3 Workflow Graph Visualization

Status: Planned

## Objective

Replace the workflow-graph placeholder in the browser dashboard with a live D3 visualization that makes phase flow, agent activity, and execution status obvious during an active session.

## Scope

- transform telemetry events into a stable graph model for phases, agents, and important transitions
- render an interactive D3 graph with pan, zoom, and clear status styling
- highlight the currently active path and failed or blocked nodes
- support click-to-inspect so selecting a node or edge opens the related event details in the existing dashboard flow
- keep live updates incremental so new events do not require a full graph rebuild on every message

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/components/session-details.tsx`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/components/workflow-graph.tsx`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/lib/telemetry-transformers.ts`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/types/telemetry.ts`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/package.json`
- `/Users/jjae/Documents/guthib/cc-deep-research/docs/REALTIME_MONITORING.md`

## Dependencies

- [033_live_session_store_and_dashboard_queries.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/033_live_session_store_and_dashboard_queries.md)
- [034_operator_dashboard_live_console.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/034_operator_dashboard_live_console.md)

## Acceptance Criteria

- the session detail page renders a graph view instead of a placeholder
- the graph shows at least phase and agent nodes with status-aware styling
- operators can identify the active execution path within a few seconds
- clicking a node or edge reveals related telemetry without reading raw JSON first
- live session updates do not cause obvious layout thrash or duplicate nodes

## Exit Criteria

- the graph answers what is running, what finished, and where execution is currently stuck
- the visualization remains usable on a normal laptop browser during a live session

## Suggested Verification

- run `npm run lint` in `dashboard/`
- manually verify the graph during a live `cc-deep-research research --enable-realtime` session
