# Task 047: Add Tool Execution Detail Drill-Down

Status: Planned

## Objective

Expose tool execution details as a first-class dashboard surface so operators can inspect arguments, outputs, latency, and failures without opening raw event JSON.

## Scope

- promote tool events into a dedicated expandable detail view or side panel
- show request and response payloads with readable formatting and safe truncation
- add duration bars or equivalent timing indicators for tool runs
- surface status, error state, and parent agent context directly in the UI
- preserve the existing generic event-details modal for unsupported event shapes

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/components/session-details.tsx`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/components/tool-execution-panel.tsx`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/lib/telemetry-transformers.ts`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/types/telemetry.ts`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/monitoring.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/docs/REALTIME_MONITORING.md`

## Dependencies

- [031_phase_agent_and_tool_instrumentation.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/031_phase_agent_and_tool_instrumentation.md)
- [032_stream_claude_cli_subprocess_events.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/032_stream_claude_cli_subprocess_events.md)
- [033_live_session_store_and_dashboard_queries.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/033_live_session_store_and_dashboard_queries.md)

## Acceptance Criteria

- tool rows or markers can be expanded into a dedicated detail view
- request parameters and response payloads are readable without horizontal overflow dominating the page
- each tool execution shows duration and terminal status
- tool failures are easy to distinguish from successful runs
- unsupported or partial payloads degrade cleanly to the existing raw JSON view

## Exit Criteria

- operators can diagnose a failed tool call from the dashboard alone in common cases
- the UI clearly connects each tool execution to its parent agent and timing context

## Suggested Verification

- run `npm run lint` in `dashboard/`
- add or update targeted telemetry tests if backend payload changes are required
- manually verify one successful and one failing tool execution in the browser
