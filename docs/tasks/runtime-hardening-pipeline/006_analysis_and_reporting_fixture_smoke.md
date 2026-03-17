# Task 006: Add Analysis And Reporting Fixture Smoke Tests

Status: Planned

## Objective

Run realistic fixture data through analyzer, deep analyzer, validator, and reporter paths to catch late-stage schema or formatting failures before full orchestration.

## Scope

- feed fixture-backed sources into analyzer and deep analyzer code paths
- verify the resulting `AnalysisResult` survives validation, reporting, and quality evaluation
- assert the report contains expected sections instead of crashing on structured intermediate data
- include at least one degraded fixture path where analysis falls back cleanly

## Target Files

- `tests/test_reporter.py`
- `tests/test_validator.py`
- `tests/test_report_quality_evaluator.py`
- `src/cc_deep_research/agents/analyzer.py`
- `src/cc_deep_research/agents/deep_analyzer.py`

## Dependencies

- [002_fixture_corpus_and_helpers.md](002_fixture_corpus_and_helpers.md)
- [003_llm_analysis_schema_contract_tests.md](003_llm_analysis_schema_contract_tests.md)

## Acceptance Criteria

- realistic analysis output can flow into report generation without runtime validation errors
- deep-analysis output merge behavior is covered with structured fixture payloads
- degraded analysis paths are explicit and tested, not accidental

## Suggested Verification

- run `uv run pytest tests/test_reporter.py tests/test_validator.py tests/test_report_quality_evaluator.py`

