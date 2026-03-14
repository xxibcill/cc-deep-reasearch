# Task 039: Add OpenRouter LLM Adapter

Status: Complete

## Objective

Implement the first direct API transport for the routing layer using OpenRouter.

## Scope

- add an OpenRouter adapter behind the shared LLM transport contract
- read API key and model defaults from the new `llm` config tree
- normalize request and response handling for prompt-based operations
- map provider-specific failures into shared LLM exceptions

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/llm/openrouter.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/llm/base.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/config.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_llm_openrouter.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_config.py`

## Dependencies

- [036_llm_route_contract_and_config.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/036_llm_route_contract_and_config.md)

## Acceptance Criteria

- OpenRouter can execute one normalized prompt request through the shared interface
- auth, timeout, and non-2xx failures are mapped into stable exceptions
- config supports provider enablement and default model selection
- tests cover success and failure paths without live network calls

## Exit Criteria

- the routing layer has one production API provider besides Claude CLI
- later tasks can route analyzer operations to OpenRouter without provider-specific branching in agents

## Suggested Verification

- run `uv run pytest tests/test_llm_openrouter.py tests/test_config.py`
