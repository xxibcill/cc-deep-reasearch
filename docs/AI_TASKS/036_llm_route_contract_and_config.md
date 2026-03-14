# Task 036: Establish LLM Route Contract And Config

Status: Complete

## Objective

Create the typed configuration and model contract for agent-level LLM routing so later tasks can add routing behavior without inventing shapes ad hoc.

## Scope

- add a dedicated `llm` config tree
- add typed models for route transport, provider type, and per-agent route plans
- keep `research.ai_integration_method` working as a compatibility bridge during migration
- do not change live agent execution behavior yet

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/config.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/models.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_config.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_models.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/docs/USAGE.md`

## Dependencies

- [016_local_runtime_boundary_completion.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/016_local_runtime_boundary_completion.md)
- [017_local_scaffolding_api_cleanup.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/017_local_scaffolding_api_cleanup.md)

## Acceptance Criteria

- config accepts `llm` settings for Claude CLI, OpenRouter, and Cerebras
- route models cover:
  - transport type
  - provider type
  - model
  - fallback order
  - per-agent route selection
- defaults are explicit and serializable
- existing config loading still works for users who only set `research.ai_integration_method`

## Exit Criteria

- later routing tasks can depend on one stable config and model surface
- no downstream task needs to redefine route payload shapes

## Suggested Verification

- run `uv run pytest tests/test_config.py tests/test_models.py`
