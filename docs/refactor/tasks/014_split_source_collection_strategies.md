# Task 014: Split Source Collection Strategies

Status: Done

## Objective

Separate sequential and parallel source collection paths so each workflow is easier to test and evolve independently.

## Scope

- move sequential collection into a dedicated strategy or service
- move parallel collection into a separate strategy or service
- keep shared aggregation and content-hydration helpers in a reusable layer

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestration/source_collection.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestration/source_collection_sequential.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestration/source_collection_parallel.py`

## Dependencies

- [013_slim_orchestrator_facade.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/013_slim_orchestrator_facade.md)

## Acceptance Criteria

- sequential and parallel workflows do not branch deeply inside one service
- fallback behavior is preserved and easier to test
- source provenance and content-fetch behavior remain unchanged

## Suggested Verification

- run `uv run pytest tests/test_orchestrator.py tests/test_orchestration.py tests/test_providers.py`
