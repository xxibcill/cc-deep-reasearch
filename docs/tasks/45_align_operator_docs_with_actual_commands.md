# Task 45: Align Operator Docs with Actual Commands and Flags

**Status: Done**

## Goal

Remove drift between docs and the current CLI or dashboard behavior.

## Scope

- compare `README.md`, `docs/USAGE.md`, and `docs/README.md` with actual command registration and flags
- fix outdated wording, examples, and environment variable guidance
- verify dashboard backend instructions still match the current command set

## Primary Files

- `README.md`
- `docs/USAGE.md`
- `docs/README.md`
- `src/cc_deep_research/cli/main.py`
- `src/cc_deep_research/cli/`

## Acceptance Criteria

- docs match real commands and options
- examples are current and runnable

## Validation

- `uv run pytest tests/test_cli_research.py -v`
- manually compare `cc-deep-research --help` and relevant subcommand help output
