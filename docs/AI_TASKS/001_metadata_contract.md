# Task 001: Stabilize Session Metadata Contract

## Objective

Define and document a stable shape for `ResearchSession.metadata` so orchestrator changes stop depending on ad hoc dictionary conventions.

## Scope

- document the expected top-level metadata keys
- define required vs optional fields
- ensure metadata written by `execute_research()` is consistent across depth modes
- make missing provider and degraded-mode cases explicit

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestrator.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/models.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/session_store.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/docs/RESEARCH_WORKFLOW.md`

## Dependencies

None.

## Acceptance Criteria

- metadata shape is documented in code or typed structures
- quick, standard, and deep runs all populate the same top-level contract
- degraded states are represented intentionally rather than by absent keys
- downstream readers in CLI/TUI can rely on the contract

## Suggested Verification

- add or update tests around `execute_research()`
- run `pytest tests/test_orchestrator.py tests/test_session_store.py`
