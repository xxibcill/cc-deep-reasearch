# Task 034: Build A Live Operator Dashboard

Status: Done

## Objective

Turn the existing Streamlit dashboard into a browser-based operator console for
active research runs, with enough detail to inspect each agent step and each
Claude CLI subprocess interaction.

## Scope

- add an active-session view with auto-refresh
- add filters for:
  - session
  - phase
  - agent
  - tool
  - provider
  - status
  - event type
- add a timeline-oriented layout that shows:
  - session summary
  - active phase
  - agent lanes or equivalent ordered lifecycle table
  - event tail
  - Claude subprocess detail pane
- surface raw stdout and stderr stream chunks in an inspectable view
- preserve the historical analytics views that already exist
- keep the UI usable on a normal laptop browser without requiring a JS rewrite

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/dashboard_app.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/telemetry.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/README.md`
- `/Users/jjae/Documents/guthib/cc-deep-research/docs/USAGE.md`

## Dependencies

- [031_phase_agent_and_tool_instrumentation.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/031_phase_agent_and_tool_instrumentation.md)
- [033_live_session_store_and_dashboard_queries.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/033_live_session_store_and_dashboard_queries.md)

## Acceptance Criteria

- an operator can open the dashboard and identify the current phase of a live
  research run within a few seconds
- agent and tool activity can be filtered and inspected without reading raw
  JSON files
- Claude subprocess output is visible in the dashboard with clear ordering and
  terminal status
- the dashboard still supports historical session drill-down after the live run
  completes

## Exit Criteria

- the browser UI answers:
  - what is running now
  - what just happened
  - which agent or subprocess is blocked
  - what Claude returned most recently
- docs show how to launch and use the live dashboard during a run

## Suggested Verification

- manually verify a monitored run with `cc-deep-research telemetry dashboard`
- add or update targeted tests for dashboard query helpers where practical
