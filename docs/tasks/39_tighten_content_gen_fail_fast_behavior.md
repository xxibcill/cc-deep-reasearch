# Task 39: Tighten Fail-Fast Behavior in Content-Gen Parsers

**Status: Done**

## Goal

Stop partial or blank LLM output from silently propagating through later stages.

## Scope

- identify stages that currently return sparse models too permissively
- fail fast for missing required fields on high-value stages
- preserve graceful degradation only where downstream behavior is intentionally tolerant

## Primary Files

- `src/cc_deep_research/content_gen/agents/`
- `src/cc_deep_research/content_gen/orchestrator.py`
- `tests/test_content_gen.py`

## Acceptance Criteria

- important missing fields cause clear errors
- tolerant stages are documented as tolerant on purpose

## Validation

- `uv run pytest tests/test_content_gen.py tests/test_iterative_loop.py -v`
