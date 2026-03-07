# Task 009: Add A Claim-Centered Analysis Model

Status: Done

## Objective

Introduce an intermediate representation for claims so synthesis is evidence-aware instead of only summary-oriented.

## Scope

- define a claim model with:
  - claim text
  - supporting sources
  - contradicting sources
  - confidence
  - freshness
  - evidence type
- update analyzer output to populate the model
- preserve source provenance for each claim

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/analyzer.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/deep_analyzer.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/models.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_models.py`

## Dependencies

- [007_source_provenance_tracking.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/007_source_provenance_tracking.md)

## Acceptance Criteria

- analysis output can explain why each key finding exists
- each claim links to evidence rather than only a final prose summary
- tests cover both supporting and contradicting evidence lists

## Suggested Verification

- run `pytest tests/test_models.py tests/test_reporter.py tests/test_validator.py`
