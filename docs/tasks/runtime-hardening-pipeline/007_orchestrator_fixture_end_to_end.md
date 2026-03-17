# Task 007: Add Orchestrator Fixture End-To-End Smoke Test

Status: Planned

## Objective

Run the orchestrator across planning, collection, analysis, validation, and session assembly using fixture-backed dependencies that preserve real pipeline contracts.

## Scope

- execute `TeamResearchOrchestrator.execute_research()` with fixture-backed provider and analysis components
- avoid fully mocking out major phases under test
- assert the final `ResearchSession` contains stable metadata, sources, analysis, validation, and report-relevant fields
- cover at least one standard-depth path and one deep-analysis path

## Target Files

- `tests/test_orchestrator.py`
- `tests/test_orchestration.py`
- `src/cc_deep_research/orchestrator.py`
- `src/cc_deep_research/orchestration/analysis_workflow.py`

## Dependencies

- [005_source_collection_fixture_integration.md](005_source_collection_fixture_integration.md)
- [006_analysis_and_reporting_fixture_smoke.md](006_analysis_and_reporting_fixture_smoke.md)

## Acceptance Criteria

- one test exercises the real orchestrator flow with fixture-backed inputs and no live provider calls
- the test would fail on late-stage schema mismatches between phases
- standard and deep modes both have at least one smoke path

## Suggested Verification

- run `uv run pytest tests/test_orchestrator.py tests/test_orchestration.py`

