# Task 005: Slim The CLI Research Command

Status: Planned

## Objective

Turn the `cc-deep-research research` command into a thin adapter that delegates to the shared research run service.

## Scope

- convert click arguments into the shared request model
- delegate execution to the shared service
- keep terminal progress and output behavior stable
- remove duplicated execution logic from the command body

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/cli/research.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/cli/shared.py`

## Dependencies

- [004_research_run_service.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/004_research_run_service.md)

## Acceptance Criteria

- the CLI command mostly parses arguments and renders terminal output
- research execution logic is no longer duplicated inside the click command
- existing CLI semantics remain intact

## Suggested Verification

- run `uv run pytest tests/test_cli_monitoring.py tests/test_orchestrator.py`

