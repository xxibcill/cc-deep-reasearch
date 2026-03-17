# Runtime Hardening Pipeline Task Pack

This task pack breaks runtime hardening into small, dependency-ordered steps aimed at reducing token and provider waste from late pipeline failures.

The target end state is:

- typed contracts exist for every LLM and provider boundary that can fail at runtime
- fixture-backed tests replay realistic Tavily and Claude payload shapes without making live network calls
- one orchestrator-level smoke path exercises the real local pipeline with recorded fixtures
- one CLI-level smoke path proves `uv run cc-deep-research research ...` can complete on fixtures without burning provider credits
- contributors have a documented preflight path to catch schema and pipeline regressions before running expensive research

Design constraints for this pack:

- prefer deterministic fixture replay over live external integration in CI
- catch boundary-shape failures as close as possible to ingestion
- keep tests cheap enough to run locally before a real research run
- avoid coupling hardening work to UI or unrelated product changes

## Task Order

1. [001_pipeline_failure_inventory.md](001_pipeline_failure_inventory.md)
2. [002_fixture_corpus_and_helpers.md](002_fixture_corpus_and_helpers.md)
3. [003_llm_analysis_schema_contract_tests.md](003_llm_analysis_schema_contract_tests.md)
4. [004_provider_response_replay_tests.md](004_provider_response_replay_tests.md)
5. [005_source_collection_fixture_integration.md](005_source_collection_fixture_integration.md)
6. [006_analysis_and_reporting_fixture_smoke.md](006_analysis_and_reporting_fixture_smoke.md)
7. [007_orchestrator_fixture_end_to_end.md](007_orchestrator_fixture_end_to_end.md)
8. [008_cli_fixture_smoke_command.md](008_cli_fixture_smoke_command.md)
9. [009_failure_path_regressions.md](009_failure_path_regressions.md)
10. [010_runtime_preflight_docs.md](010_runtime_preflight_docs.md)

