# Task 002: Extract Config Override Normalization

Status: Planned

## Objective

Move CLI-specific config mutation logic into a reusable helper that can be called by both CLI and API entrypoints.

## Scope

- normalize research request options into `Config` changes
- preserve current flag semantics for providers, team size, cross-reference, and parallel mode
- keep the helper narrow: request in, config out

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/research_runs/options.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/cli/research.py`

## Dependencies

- [001_shared_research_run_contract.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/001_shared_research_run_contract.md)

## Acceptance Criteria

- request option handling is no longer embedded directly inside the CLI command body
- the helper is reusable by the future API entrypoint
- current CLI behavior stays unchanged

## Suggested Verification

- run `uv run pytest tests/test_config.py tests/test_cli_monitoring.py`

