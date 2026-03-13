# Task 035: Finalize Monitoring CLI, Docs, And End-To-End Validation

Status: Done

## Objective

Lock in the live monitoring workflow with clear CLI ergonomics, documentation,
and end-to-end verification so contributors can rely on the browser monitor as
part of normal harness development.

## Scope

- review current CLI entry points and add any missing flags or commands needed
  for live monitoring
- document the intended operator workflow:
  - start a monitored research run
  - open the dashboard
  - inspect active phases and Claude subprocess output
  - review persisted telemetry after completion
- add integration tests or fixtures for the new telemetry contract where
  practical
- run an end-to-end monitored session and record any gaps that still prevent
  operator use
- ensure failure modes are documented:
  - missing Streamlit dependencies
  - no telemetry yet
  - nested Claude session fallback
  - timeout and subprocess failure visibility

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/cli.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/README.md`
- `/Users/jjae/Documents/guthib/cc-deep-research/docs/USAGE.md`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/`

## Dependencies

- [031_phase_agent_and_tool_instrumentation.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/031_phase_agent_and_tool_instrumentation.md)
- [032_stream_claude_cli_subprocess_events.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/032_stream_claude_cli_subprocess_events.md)
- [033_live_session_store_and_dashboard_queries.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/033_live_session_store_and_dashboard_queries.md)
- [034_operator_dashboard_live_console.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/034_operator_dashboard_live_console.md)

## Acceptance Criteria

- the monitored workflow can be started and observed with documented commands
- docs describe both the happy path and common failure modes
- there is an end-to-end verification path that exercises live monitoring,
  telemetry persistence, and dashboard inspection
- the observability task pack leaves a clear handoff for future refinements

## Exit Criteria

- a contributor can follow the docs and successfully observe a research run in
  the browser without reading implementation code
- verification evidence exists for both live monitoring and post-run telemetry
  review
- remaining limitations are explicitly documented rather than implicit

## Suggested Verification

- run targeted `uv run pytest ...` for affected monitoring, telemetry, CLI, and
  dashboard tests
- manually verify one full monitored research run and one failure-mode run
