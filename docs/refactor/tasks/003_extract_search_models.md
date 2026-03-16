# Task 003: Extract Search Models

Status: Done

## Objective

Move search-related types out of the monolithic model module into a dedicated search-domain module.

## Scope

- extract `ResearchDepth`, `SearchOptions`, `QueryProvenance`, `SearchResultItem`, `SearchResult`, `QueryProfile`, and `QueryFamily`
- keep validation behavior intact
- update internal imports without changing external behavior

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/models.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/models/search.py`

## Dependencies

- [001_add_refactor_safety_net.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/001_add_refactor_safety_net.md)

## Acceptance Criteria

- search-domain types live in one module with coherent responsibilities
- all existing imports continue to work through a compatibility layer or staged import updates
- tests for search, providers, and orchestration remain green

## Suggested Verification

- run `uv run pytest tests/test_models.py tests/test_providers.py tests/test_orchestrator.py`
