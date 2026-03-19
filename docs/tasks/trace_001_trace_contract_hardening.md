# Task 001: Harden The Trace Contract

Status: Done

## Objective

Make the trace stream semantically strong enough that operators do not need to infer core meaning from free-form metadata. This task should establish the event contract needed to answer:

- what happened
- why it happened
- what state changed
- where execution degraded

## Scope

- add a versioned trace schema for high-value telemetry events
- add first-class semantic events:
  - `decision.made`
  - `state.changed`
  - `degradation.detected`
- extend existing emitted events so important fields are explicit instead of inferred later
- normalize reason and severity fields used by failures, fallbacks, and degraded outcomes
- keep backward compatibility for existing dashboards where feasible, but prefer a clean forward contract

## Required Event Fields

These fields should exist on all high-value events or be populated by a normalization layer:

- `trace_version`
- `run_id` when browser-started runs exist, otherwise explicit null
- `session_id`
- `event_id`
- `parent_event_id`
- `cause_event_id`
- `sequence_number`
- `timestamp`
- `phase`
- `operation`
- `attempt`
- `actor_type`
- `actor_id`
- `severity`
- `reason_code`
- `degraded`

## New Event Contracts

### `decision.made`

Use for planner, routing, follow-up, and stop decisions.

Required metadata:

- `decision_type`
- `reason_code`
- `chosen_option`
- `inputs`

Optional metadata:

- `rejected_options`
- `cause_event_ids`
- `confidence`

### `state.changed`

Use for explicit before/after transitions instead of requiring session-store diffs.

Required metadata:

- `state_scope`
- `state_key`
- `before`
- `after`
- `change_type`

Optional metadata:

- `caused_by_event_id`
- `checkpoint`

### `degradation.detected`

Use for successful-but-impaired execution and partial recovery paths.

Required metadata:

- `reason_code`
- `severity`
- `scope`

Optional metadata:

- `recoverable`
- `mitigation`
- `caused_by_event_id`
- `impact`

## Target Files

- `src/cc_deep_research/monitoring.py`
- `src/cc_deep_research/orchestration/phases.py`
- `src/cc_deep_research/orchestration/runtime.py`
- `src/cc_deep_research/orchestration/session_state.py`
- `src/cc_deep_research/llm/router.py`
- `src/cc_deep_research/llm/base.py`
- `src/cc_deep_research/llm/claude_cli.py`
- `src/cc_deep_research/telemetry/live.py`
- `src/cc_deep_research/telemetry/query.py`
- `src/cc_deep_research/telemetry/__init__.py`

## Implementation Notes

- avoid pushing more semantics into frontend inference; emit or normalize them in Python first
- keep reason codes stable and enumerable; do not rely on arbitrary human strings for machine logic
- reuse existing event families where possible, but do not overload unrelated event types
- preserve ordered append-only writes to `events.jsonl`
- ensure old events can still be read by live-query helpers without crashing

## Acceptance Criteria

- a run emits explicit semantic events for major decisions, state transitions, and degradations
- phase and operation context no longer depends only on frontend inference
- failure and fallback reasons expose normalized `reason_code` and `severity`
- saved session metadata and telemetry agree on degraded execution state
- older telemetry can still be read safely through normalization paths

## Suggested Verification

- add focused tests in `tests/test_monitoring.py`
- add live/historical normalization coverage in `tests/test_telemetry.py`
- add orchestration-level assertions in `tests/test_orchestrator.py`
- verify one real run still writes valid `events.jsonl` and `summary.json`

## Dependencies

- none

## Out Of Scope

- compare mode UI
- replay bundle export/import
- large dashboard redesign
