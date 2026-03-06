# Task 005: Upgrade Query Intent Classification

## Objective

Improve `ResearchLeadAgent.analyze_query()` so retrieval strategy is driven by explicit query intent instead of shallow heuristics.

## Scope

- classify at least:
  - informational
  - comparative
  - time-sensitive
  - evidence-seeking
- infer likely source classes such as news, academic, official docs, and market analysis
- expose the classification in strategy output

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/research_lead.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/models.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_teams.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_orchestrator.py`

## Dependencies

- [002_phase_result_types.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/002_phase_result_types.md)

## Acceptance Criteria

- strategy output includes intent and target source classes
- classification is deterministic and covered by tests
- time-sensitive prompts are tagged without depending on current year literals only

## Suggested Verification

- run `pytest tests/test_teams.py tests/test_orchestrator.py`
