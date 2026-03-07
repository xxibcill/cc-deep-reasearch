# Task 007: Persist Query Provenance On Sources

Status: Done

## Objective

Record which query family and query variation produced each source so later validation and reporting can reason about evidence provenance.

## Scope

- extend source metadata with query provenance fields
- preserve provenance through aggregation and deduplication
- surface provenance in session metadata or analysis payloads

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/source_collector.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/aggregation.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/models.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_models.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_providers.py`

## Dependencies

- [006_query_family_expansion.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/006_query_family_expansion.md)

## Acceptance Criteria

- every collected source can be traced back to its query variation
- aggregation does not drop provenance unexpectedly
- tests cover duplicate URLs returned by multiple query families

## Suggested Verification

- run `pytest tests/test_models.py tests/test_providers.py tests/test_orchestrator.py`
