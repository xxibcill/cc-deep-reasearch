# Task 046: Build The Agent Timeline Swimlane View

Status: Planned

## Objective

Turn the timeline placeholder into a swimlane view that shows concurrent agent activity over time so operators can understand overlap, stalls, and hand-offs without scanning the raw event stream.

## Scope

- derive agent execution spans from live telemetry with start, finish, and status state
- render a time-axis swimlane view that supports concurrent agent runs
- show tool and phase markers inside or alongside each lane when useful
- add hover or click inspection for duration, status, and related event metadata
- support filtering so operators can focus on one phase or one agent without losing the overall timeline context

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/components/session-details.tsx`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/components/agent-timeline.tsx`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/lib/telemetry-transformers.ts`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/types/telemetry.ts`
- `/Users/jjae/Documents/guthib/cc-deep-research/docs/REALTIME_MONITORING.md`

## Dependencies

- [031_phase_agent_and_tool_instrumentation.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/031_phase_agent_and_tool_instrumentation.md)
- [033_live_session_store_and_dashboard_queries.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/033_live_session_store_and_dashboard_queries.md)
- [034_operator_dashboard_live_console.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/034_operator_dashboard_live_console.md)

## Acceptance Criteria

- the timeline view shows one lane per active or completed agent with a shared time axis
- parallel work is visually distinct instead of serialized into a flat event list
- duration, status, and phase context are inspectable from each lane or segment
- operators can filter the timeline by phase or agent without breaking live updates

## Exit Criteria

- the dashboard answers which agents ran in parallel, which one is still active, and where idle gaps occurred
- the timeline remains readable for sessions with dozens of events and multiple agents

## Suggested Verification

- run `npm run lint` in `dashboard/`
- manually verify at least one session with overlapping agent activity in the live dashboard
