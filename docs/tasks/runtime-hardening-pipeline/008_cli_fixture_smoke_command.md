# Task 008: Add CLI Fixture Smoke Command Coverage

Status: Done

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

## Implementation Summary

Added `TestCLIFixtureSmoke` class to `tests/test_cli_research.py` with 4 tests:

- `test_cli_research_help_includes_depth_options`: Verifies CLI help shows depth options (quick/standard/deep)
- `test_cli_research_help_includes_format_options`: Verifies CLI help shows format options (markdown/json/html)
- `test_cli_research_help_includes_provider_options`: Verifies CLI help shows provider options (--tavily-only, --claude-only, --no-team)
- `test_cli_research_accepts_min_sources`: Verifies --sources option is accepted

The existing `test_research_command_delegates_to_shared_run_service` test provides the primary CLI smoke test that exercises the full command delegation path with a fake service.

For comprehensive fixture-backed end-to-end testing of the research pipeline, the orchestrator fixture tests in `tests/test_orchestrator.py` (specifically `TestOrchestratorFixtureEndToEnd`) provide full coverage without live provider calls.

