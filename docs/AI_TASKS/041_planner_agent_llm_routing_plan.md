# Task 041: Let The Planner Emit An Agent LLM Plan

Status: Complete

## Objective

Extend strategy planning so one session can produce a per-agent LLM route plan based on availability and task shape.

## Scope

- add `llm_plan` to strategy output
- keep `ResearchLeadAgent` itself heuristic in v1 to avoid bootstrap recursion
- inspect route availability:
  - Claude CLI executable presence
  - `CLAUDECODE` nested-session constraint
  - OpenRouter config readiness
  - Cerebras config readiness
- update the session route registry after planning completes

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/research_lead.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestration/planning.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestration/runtime.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/models.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_orchestrator.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_planning.py`

## Dependencies

- [036_llm_route_contract_and_config.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/036_llm_route_contract_and_config.md)
- [037_session_llm_route_registry.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/037_session_llm_route_registry.md)

## Acceptance Criteria

- strategy output includes a typed per-agent route plan
- planner avoids selecting Claude CLI as primary when unavailable or blocked by nested session rules
- planner can prefer OpenRouter and Cerebras when configured
- registry is updated from planner output before analyzer execution begins

## Exit Criteria

- the planner, not static config alone, becomes the owner of session-specific route selection
- downstream agents can execute against routes chosen during planning

## Suggested Verification

- run `uv run pytest tests/test_planning.py tests/test_orchestrator.py`
