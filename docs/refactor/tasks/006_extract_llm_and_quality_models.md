# Task 006: Extract LLM And Quality Models

Status: Done

## Objective

Split LLM route types and quality/evidence types into focused modules so those contracts stop inflating the main model surface.

## Scope

- extract LLM route models into `models/llm.py`
- extract `QualityScore`, claim evidence, freshness, and evidence typing into `models/quality.py`
- update reporting and LLM modules to import from the new boundaries

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/models.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/models/llm.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/models/quality.py`

## Dependencies

- [004_extract_analysis_models.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/004_extract_analysis_models.md)
- [005_extract_session_models.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/005_extract_session_models.md)

## Acceptance Criteria

- LLM and quality contracts have dedicated modules
- reporting and routing code no longer depend on one umbrella model file
- claim-evidence behavior stays unchanged

## Suggested Verification

- run `uv run pytest tests/test_models.py tests/test_llm_registry.py tests/test_llm_router.py tests/test_report_quality_evaluator.py`
