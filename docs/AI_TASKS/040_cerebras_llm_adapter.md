# Task 040: Add Cerebras LLM Adapter

Status: Complete

## Objective

Implement Cerebras as the second direct API transport behind the shared LLM routing contract.

## Scope

- add a Cerebras adapter with the same interface as OpenRouter
- support config-driven base URL, API key, timeout, and default model
- keep response normalization and exception mapping provider-neutral
- do not change planner or agent execution yet

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/llm/cerebras.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/llm/base.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/config.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_llm_cerebras.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_config.py`

## Dependencies

- [036_llm_route_contract_and_config.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/036_llm_route_contract_and_config.md)

## Acceptance Criteria

- Cerebras can execute one normalized prompt request through the shared interface
- failures map into the same shared exception taxonomy used by other transports
- config supports provider enablement and default model selection
- tests cover success and failure paths without live network calls

## Exit Criteria

- the routing layer has both requested API providers available for planner selection
- later tasks can assign low-latency structured work to Cerebras without bespoke integration code

## Suggested Verification

- run `uv run pytest tests/test_llm_cerebras.py tests/test_config.py`
