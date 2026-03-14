# Task 038: Extract Claude CLI Transport Adapter

Status: Complete

## Objective

Move the current Claude Code CLI subprocess logic into a reusable LLM transport adapter that fits the new routing layer.

## Scope

- extract Claude CLI request execution into `src/cc_deep_research/llm/claude_cli.py`
- preserve streamed subprocess telemetry and nested-session protection
- keep existing parsing behavior in analysis code
- avoid changing planner behavior in this task

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/llm/claude_cli.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/llm_analysis_client.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/monitoring.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_llm_analysis_client.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_monitoring.py`

## Dependencies

- [032_stream_claude_cli_subprocess_events.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/032_stream_claude_cli_subprocess_events.md)
- [036_llm_route_contract_and_config.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/036_llm_route_contract_and_config.md)

## Acceptance Criteria

- Claude CLI execution lives behind a reusable transport abstraction
- streamed subprocess events still emit in sequence
- timeout, failed-to-start, and nested-session cases behave as they do now
- existing analysis prompts and response parsing still work

## Exit Criteria

- Claude CLI is no longer hardwired as an analysis-only implementation detail
- other tasks can consume the CLI path through the new LLM layer

## Suggested Verification

- run `uv run pytest tests/test_llm_analysis_client.py tests/test_monitoring.py`
