# Task 011: Remove Architecture Mismatch

Status: Done

## Objective

Make the codebase honest about whether it is running a local pipeline or a real coordination layer.

## Scope

- pick the near-term direction from the improvement plan
- if staying local, rename or document placeholder coordination abstractions
- if building a real coordination layer, define task and result envelopes first
- align docs with actual execution behavior

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/teams/research_team.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/coordination/agent_pool.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/coordination/message_bus.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestrator.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/docs/RESEARCH_WORKFLOW.md`
- `/Users/jjae/Documents/guthib/cc-deep-research/docs/USAGE.md`

## Dependencies

- [003_orchestrator_contract_tests.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/003_orchestrator_contract_tests.md)

## Acceptance Criteria

- code and docs describe the same runtime model
- misleading placeholder abstractions are either renamed, documented, or completed
- contributor-facing docs stop implying capabilities that do not exist

## Suggested Verification

- run `pytest tests/test_teams.py tests/test_orchestrator.py`
