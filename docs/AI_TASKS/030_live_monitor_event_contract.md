# Task 030: Define A Live Monitor Event Contract

Status: Done

## Objective

Create a stable telemetry contract for live workflow monitoring so every event
in a research run can be correlated, filtered, and rendered in a browser.

## Scope

- define the event fields required for live monitoring:
  - event id
  - parent event id
  - session id
  - sequence number or ordering field
  - category
  - event type
  - name
  - status
  - agent id
  - timestamps and duration
  - structured metadata payload
- define parent-child relationships for:
  - session
  - phase
  - agent lifecycle
  - search/provider calls
  - tool calls
  - reasoning summaries
  - Claude CLI subprocess events
- update telemetry persistence and query helpers to preserve the new fields
- keep the contract backward-compatible enough that older sessions do not crash
  the dashboard

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/monitoring.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/telemetry.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_monitoring.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_telemetry.py`

## Dependencies

- [015_observability_and_stop_reasons.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/015_observability_and_stop_reasons.md)

## Acceptance Criteria

- every emitted event has a stable identifier and a deterministic session-level
  ordering field
- child events can reference a parent event without requiring dashboard-side
  guesswork
- telemetry ingestion stores and returns the new correlation fields
- older telemetry sessions without the new fields remain queryable

## Exit Criteria

- monitor APIs expose a documented event schema that covers live and persisted
  events
- tests assert parent-child correlation and ordering behavior
- the dashboard query layer can fetch events without losing the new fields

## Suggested Verification

- run `uv run pytest tests/test_monitoring.py tests/test_telemetry.py`

