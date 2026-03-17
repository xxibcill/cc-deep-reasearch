# Task 003: Add LLM Analysis Schema Contract Tests

Status: Planned

## Objective

Lock down the shapes accepted at the analysis boundaries so malformed Claude responses fail fast in tests instead of during expensive runs.

## Scope

- add contract tests for theme extraction, cross-reference analysis, gap detection, and synthesized findings
- validate both parser output and downstream model validation behavior
- cover tolerant normalization where the code intentionally accepts structured objects and converts them into stable internal types
- add negative tests for malformed or missing keys that should trigger controlled fallback or explicit errors

## Target Files

- `tests/test_llm_analysis_client.py`
- `tests/test_models.py`
- `tests/test_reporter.py`
- `src/cc_deep_research/agents/llm_analysis_client.py`
- `src/cc_deep_research/models/analysis.py`

## Dependencies

- [002_fixture_corpus_and_helpers.md](002_fixture_corpus_and_helpers.md)

## Acceptance Criteria

- every LLM analysis parser has at least one fixture-backed happy-path contract test
- known malformed payload shapes are covered by regression tests
- a future change that reintroduces dicts into string-only report fields fails in tests before runtime

## Suggested Verification

- run `uv run pytest tests/test_llm_analysis_client.py tests/test_models.py tests/test_reporter.py`

