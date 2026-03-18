# Task 007: Add Orchestrator Fixture End-To-End Smoke Test

Status: Done

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

## Implementation Summary

Added `TestOrchestratorFixtureEndToEnd` class to `tests/test_orchestrator.py` with 3 tests:

- `test_standard_depth_end_to_end_smoke`: Tests STANDARD depth mode with fixture-backed components, verifying:
  - Complete session metadata contract (strategy, analysis, validation, iteration_history, providers, execution, deep_analysis, llm_routes)
  - Provider status is ready
  - Deep analysis status is "not_requested"
  - Query family provenance is preserved
  - Sources contain proper provenance metadata

- `test_deep_analysis_end_to_end_smoke`: Tests DEEP analysis mode with fixture-backed components, verifying:
  - Complete session metadata contract
  - Deep analysis status is "completed"
  - Cross-referencing is enabled in strategy
  - Multiple query families are used

- `test_session_schema_contract_across_phases`: Verifies late-stage schema mismatches between phases are caught by checking all expected metadata keys and nested fields are present and properly typed.

