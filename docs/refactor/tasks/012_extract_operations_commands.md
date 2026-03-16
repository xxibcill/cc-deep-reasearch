# Task 012: Extract Operations Commands

Status: Planned

## Objective

Move session, config, telemetry, benchmark, and dashboard commands into separate CLI modules.

## Scope

- extract operational commands from the main CLI file
- group related commands by responsibility
- keep command names and output contracts stable

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/cli.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/cli/session.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/cli/config.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/cli/telemetry.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/cli/benchmark.py`

## Dependencies

- [010_extract_cli_bootstrap.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/010_extract_cli_bootstrap.md)

## Acceptance Criteria

- operational commands are no longer mixed with research execution code
- command-specific helpers live next to their commands
- the CLI file size drops materially without breaking command discovery

## Suggested Verification

- run `uv run pytest tests/test_benchmark.py tests/test_config.py tests/test_session_store.py tests/test_telemetry.py`
