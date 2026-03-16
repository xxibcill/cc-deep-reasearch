# Task 004: Extract Analysis Models

Status: Done

## Objective

Move analysis and validation types into a dedicated analysis-domain module so reporting and orchestration do not depend on one oversized model file.

## Scope

- extract `StrategyPlan`, `StrategyResult`, `AnalysisFinding`, `AnalysisGap`, `AnalysisResult`, `ValidationResult`, and `IterationHistoryRecord`
- keep existing field names and validation behavior stable
- limit the task to model movement and import updates

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/models.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/models/analysis.py`

## Dependencies

- [001_add_refactor_safety_net.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/001_add_refactor_safety_net.md)
- [003_extract_search_models.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/003_extract_search_models.md)

## Acceptance Criteria

- analysis-domain types are isolated from unrelated session and LLM types
- reporters, validators, and orchestrators import from clear boundaries
- no behavioral regressions are introduced during the move

## Suggested Verification

- run `uv run pytest tests/test_models.py tests/test_reporter.py tests/test_validator.py tests/test_orchestrator.py`
