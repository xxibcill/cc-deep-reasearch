# Task 009: Extract Config IO

Status: Planned

## Objective

Move config file paths, env parsing, load/save helpers, and default generation into dedicated I/O helpers.

## Scope

- extract `get_default_config_path()`, env parsing helpers, `load_config()`, `save_config()`, and default-file creation helpers
- keep CLI and runtime call sites unchanged where possible
- avoid changing the on-disk config contract

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/config.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/config/io.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/config/defaults.py`

## Dependencies

- [008_split_config_schema.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/008_split_config_schema.md)

## Acceptance Criteria

- schema and I/O responsibilities are separated
- config file behavior remains unchanged
- callers no longer need to import one large module for unrelated config concerns

## Suggested Verification

- run `uv run pytest tests/test_config.py tests/test_cli_monitoring.py`
