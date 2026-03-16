# Task 010: Extract CLI Bootstrap

Status: Done

## Objective

Reduce the top-level CLI file to a small command registration module.

## Scope

- move shared CLI helpers and command registration into a `cli/` package
- keep the package entrypoint and Click group stable
- do not change end-user flags in this task

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/cli.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/cli/main.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/cli/shared.py`

## Dependencies

- [001_add_refactor_safety_net.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/001_add_refactor_safety_net.md)
- [009_extract_config_io.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/009_extract_config_io.md)

## Acceptance Criteria

- the top-level CLI entrypoint is mostly command registration
- shared helper functions are moved out of the Click command definitions
- the installed script entrypoint remains unchanged

## Suggested Verification

- run `uv run pytest tests/test_cli_monitoring.py tests/test_session_store.py`
