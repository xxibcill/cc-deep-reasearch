# Task 008: Split Config Schema

Status: Planned

## Objective

Separate configuration type definitions from configuration loading logic.

## Scope

- move Pydantic config models into a schema-focused module tree
- keep field names, defaults, and validation semantics unchanged
- leave file I/O, env parsing, and persistence for the next task

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/config.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/config/schema.py`

## Dependencies

- [001_add_refactor_safety_net.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/001_add_refactor_safety_net.md)

## Acceptance Criteria

- config types live separately from side-effecting logic
- config consumers import schema classes from a clear module boundary
- validation behavior stays backward compatible

## Suggested Verification

- run `uv run pytest tests/test_config.py tests/test_llm_registry.py`
