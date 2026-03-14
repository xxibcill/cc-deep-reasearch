# Task 043: Record LLM Route Telemetry And Session Metadata

Status: Complete

## Objective

Make planner-selected and actually used LLM routes visible in telemetry, dashboard analytics, and persisted session metadata.

## Scope

- add provider-neutral LLM route events
- record route selection, fallback, completion, and failure
- persist planned and actual route usage in session metadata
- keep Claude CLI subprocess chunk events attached under the higher-level request flow

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/monitoring.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestration/session_state.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/telemetry.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/dashboard_app.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_monitoring.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_telemetry.py`

## Dependencies

- [037_session_llm_route_registry.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/037_session_llm_route_registry.md)
- [038_claude_cli_transport_adapter.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/038_claude_cli_transport_adapter.md)
- [042_analysis_service_llm_router_integration.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/042_analysis_service_llm_router_integration.md)

## Acceptance Criteria

- telemetry exposes:
  - selected route
  - fallback transitions
  - provider
  - transport
  - model
  - agent id
- session metadata records both planned routes and actual route usage summaries
- dashboard analytics can distinguish CLI-backed and API-backed LLM work
- existing Claude subprocess events still appear with parent-child correlation

## Exit Criteria

- operators can tell which agent used which route in a mixed session
- persisted sessions explain degraded runs caused by route failures or fallback

## Suggested Verification

- run `uv run pytest tests/test_monitoring.py tests/test_telemetry.py`
