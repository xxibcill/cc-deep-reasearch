# Task 30: Snapshot the Current Session Metadata Contract

**Status: Done**

## Goal

Document the exact metadata shape produced by the research pipeline today.

## Scope

- inspect the orchestrator and session builder paths
- list required and optional metadata keys
- capture nested shapes for strategy, analysis, validation, execution, and iteration history

## Primary Files

- `src/cc_deep_research/orchestrator.py`
- `src/cc_deep_research/orchestration/session_state.py`
- `src/cc_deep_research/models/session.py`
- `docs/RESEARCH_WORKFLOW.md`

## Acceptance Criteria

- one doc section or inline contract note describes the current metadata shape
- required versus optional fields are called out
- no behavior change yet

## Validation

- `uv run pytest tests/test_orchestrator.py tests/test_orchestration.py -v`
