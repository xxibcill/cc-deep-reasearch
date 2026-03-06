# Task 006: Generate Query Families Instead Of Ad Hoc Variants

## Objective

Refactor query expansion so each variation has a purpose and label rather than being a loose string permutation.

## Scope

- generate query families such as:
  - baseline
  - primary-source
  - expert-analysis
  - current-updates
  - opposing-view or risk
- attach intent tags to each generated query
- keep the original query in the output
- deduplicate semantically repetitive variants

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/query_expander.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/models.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_orchestrator.py`

## Dependencies

- [005_query_intent_classification.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/005_query_intent_classification.md)

## Acceptance Criteria

- expansion output includes both query text and family metadata
- time-sensitive prompts produce freshness-aware variants
- comparison prompts produce contrast-oriented variants
- repetitive variants are reduced compared with the current implementation

## Suggested Verification

- run `pytest tests/test_orchestrator.py`
