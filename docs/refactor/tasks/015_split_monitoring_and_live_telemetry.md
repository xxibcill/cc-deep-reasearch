# Task 015: Split Monitoring And Live Telemetry

Status: Done

## Objective

Decouple event emission from live telemetry file reading and dashboard shaping.

## Scope

- keep `ResearchMonitor` focused on emitting and persisting events
- move live-session snapshot reads and event-tree shaping out of the telemetry monolith
- avoid changing event payload structure in this task

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/monitoring.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/telemetry.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/telemetry/live.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/telemetry/tree.py`

## Dependencies

- [001_add_refactor_safety_net.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/001_add_refactor_safety_net.md)

## Acceptance Criteria

- monitor responsibilities stop at event generation and persistence
- live telemetry readers live in dedicated modules
- event-tree queries keep returning the same contract

## Suggested Verification

- run `uv run pytest tests/test_monitoring.py tests/test_telemetry.py`
