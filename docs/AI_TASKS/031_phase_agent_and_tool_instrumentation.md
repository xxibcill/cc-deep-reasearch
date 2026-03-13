# Task 031: Expand Phase, Agent, And Tool Instrumentation

Status: Done

## Objective

Emit detailed lifecycle events for the orchestrator and local agents so the
browser monitor shows what the workflow is doing at each step, not just the
final outcome of each phase.

## Scope

- instrument orchestrator phases with explicit start, progress, success, and
  failure events
- add richer agent lifecycle events for:
  - team initialization
  - researcher spawn/start/progress/complete/fail
  - source collection
  - analysis
  - validation
  - reporting
- ensure provider calls and content-fetch steps are attached to the right parent
  phase or agent
- normalize metadata so event consumers do not need per-call special cases
- avoid duplicating console-only messages that do not belong in structured
  telemetry

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestrator.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestration/phases.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestration/execution.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestration/source_collection.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/researcher.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/source_collector.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_orchestrator.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_monitoring.py`

## Dependencies

- [030_live_monitor_event_contract.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/030_live_monitor_event_contract.md)

## Acceptance Criteria

- a monitored run produces enough structured events to reconstruct the full
  workflow timeline in order
- each major phase emits started and finished events
- each spawned researcher produces identifiable lifecycle events tied to its
  query or task id
- tool and provider events can be grouped under the phase or agent that caused
  them

## Exit Criteria

- a single session event stream can answer:
  - which phase is active now
  - which agents are running
  - which tool call is in flight
  - which step failed and why
- tests cover both success and failure or timeout cases for instrumented flows

## Suggested Verification

- run `uv run pytest tests/test_orchestrator.py tests/test_monitoring.py`

