# Task 004: Build Shared Research Run Service

Status: Complete

## Objective

Create a single service that owns end-to-end research execution for both CLI and server callers.

## Scope

- load config
- apply normalized request overrides
- create monitor and orchestrator
- execute research
- materialize output artifacts
- return typed results

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/research_runs/service.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/research_runs/__init__.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/cli/shared.py`

## Dependencies

- [001_shared_research_run_contract.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/001_shared_research_run_contract.md)
- [002_config_override_normalization.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/002_config_override_normalization.md)
- [003_report_output_materialization.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/003_report_output_materialization.md)

## Acceptance Criteria

- one service can execute a research run without depending on Click or FastAPI
- terminal UI concerns are passed in as optional adapters instead of being embedded in the service
- the service exposes enough result data for CLI and API callers to present different UX layers

## Suggested Verification

- run `uv run pytest tests/test_orchestrator.py tests/test_reporter.py tests/test_session_store.py`
