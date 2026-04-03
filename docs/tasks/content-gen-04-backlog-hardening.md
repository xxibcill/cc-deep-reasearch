# Task 04: Harden Backlog and Early Ideation Stages (Partially Implemented)

## Status

Current status: Partially implemented

Implemented today:

- Backlog generation already accepts `OpportunityBrief` and the prompt includes its fields when present.
- Backlog and scoring parsers have regression tests for malformed and partial responses.
- Invalid scoring recommendations are normalized to `hold` instead of propagating arbitrary values.

Remaining gaps:

- Empty or malformed backlog/scoring output mainly results in warnings and sparse outputs, not explicit degraded or failed states.
- Zero valid ideas do not trigger a clear failure path in the orchestrator.
- Trace warnings/errors are not populated from degraded backlog or scoring conditions.

## Goal

Make backlog build and idea scoring more reliable, stricter, and easier to debug.

## Why

Early content-gen stages currently parse brittle plain-text output and can degrade into sparse results without enough signal.

## Scope

In scope:

- improve backlog parsing and validation
- improve scoring validation
- expose degraded or malformed-output conditions
- make backlog generation consume the new `OpportunityBrief`

Out of scope:

- changing shortlist selection behavior
- dashboard UI changes

## Suggested File Targets

- `src/cc_deep_research/content_gen/agents/backlog.py`
- `src/cc_deep_research/content_gen/prompts/backlog.py`
- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/orchestrator.py`
- `tests/test_content_gen.py`

## Acceptance Criteria

- backlog prompt uses `OpportunityBrief` inputs when available
- empty or malformed backlog output is surfaced clearly
- scoring output cannot silently return invalid recommendations
- degraded cases can be reflected in trace warnings or errors

## Testing

Add tests for:

- malformed backlog response
- malformed scoring response
- `OpportunityBrief` fields included in backlog prompt
- clear failure path when zero valid ideas are parsed

## Notes For Small Agent

Keep parser changes incremental. Do not rewrite the whole agent stack in this task.
