# Task 008: Add A Second Retrieval Path

## Objective

Reduce dependence on a single retrieval path by adding either a second provider or a richer alternative Tavily strategy mode behind the provider abstraction.

## Scope

- keep the normalized provider interface intact
- add one additional retrieval option
- make configuration explicit
- preserve graceful degradation when the new path is unavailable

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/providers/__init__.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/source_collector.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/config.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_providers.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_tavily_provider.py`

## Dependencies

- [003_orchestrator_contract_tests.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/003_orchestrator_contract_tests.md)

## Acceptance Criteria

- at least two retrieval modes can be selected through config
- a missing or failing provider degrades cleanly instead of collapsing the run
- tests cover selection and failure behavior

## Suggested Verification

- run `pytest tests/test_providers.py tests/test_tavily_provider.py tests/test_orchestrator.py`
