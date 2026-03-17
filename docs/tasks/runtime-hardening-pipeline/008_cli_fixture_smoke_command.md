# Task 008: Add CLI Fixture Smoke Command Coverage

Status: Planned

## Objective

Prove the user-facing `research` command can complete against fixture-backed runtime paths before anyone spends live provider credits.

## Scope

- add a CLI smoke test that drives the real command entrypoint against a fixture-backed research run
- preserve the normal CLI formatting and output materialization path
- add a documented low-cost local command or profile that contributors can run before expensive queries
- keep this path in-process and deterministic

## Target Files

- `tests/test_cli_research.py`
- `src/cc_deep_research/cli/research.py`
- `src/cc_deep_research/cli/shared.py`
- `src/cc_deep_research/research_runs/service.py`

## Dependencies

- [007_orchestrator_fixture_end_to_end.md](007_orchestrator_fixture_end_to_end.md)

## Acceptance Criteria

- there is one deterministic smoke test for the `research` command that does more than command delegation
- contributors have one cheap preflight command that exercises the pipeline without live providers
- the smoke path catches regressions in CLI wiring and result materialization

## Suggested Verification

- run `uv run pytest tests/test_cli_research.py tests/test_research_run_service.py`

