# Task 032: Stream Claude CLI Subprocess Events

Status: Done

## Objective

Replace black-box Claude CLI analysis calls with streamed subprocess telemetry
so the monitor can show how the harness invokes Claude Code CLI and how the
process responds over time.

## Scope

- replace blocking `subprocess.run` in the Claude analysis path with streamed
  subprocess handling
- emit structured events for:
  - subprocess scheduled
  - subprocess started
  - stdout chunk received
  - stderr chunk received
  - subprocess completed
  - subprocess timeout
  - subprocess failed to start
- capture command metadata safely:
  - executable path
  - model
  - operation name
  - timeout
  - exit code
- attach streamed subprocess events to the relevant LLM operation and parent
  workflow step
- preserve current parsing behavior for the final Claude response
- avoid logging secrets or full prompts unless explicitly redacted or truncated

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/llm_analysis_client.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/ai_analysis_service.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/monitoring.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_llm_analysis_client.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_monitoring.py`

## Dependencies

- [030_live_monitor_event_contract.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/030_live_monitor_event_contract.md)

## Acceptance Criteria

- Claude CLI invocations no longer appear as a single opaque success event
- stdout and stderr chunks are emitted in sequence while the subprocess is
  running
- timeout and non-zero exit cases emit terminal events with useful metadata
- final response parsing still succeeds for healthy Claude runs

## Exit Criteria

- an operator can see when Claude was invoked, what operation it served, and
  how the subprocess progressed before completion
- tests simulate streamed stdout, streamed stderr, timeout, and non-zero exit
  paths
- no secret-bearing prompt text is stored verbatim unless intentionally allowed
  by a documented policy

## Suggested Verification

- run `uv run pytest tests/test_llm_analysis_client.py tests/test_monitoring.py`
