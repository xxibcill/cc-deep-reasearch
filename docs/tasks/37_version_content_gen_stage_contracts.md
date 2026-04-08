# Task 37: Version the Content-Gen Stage Contracts

**Status: Done**

## Goal

Make prompt-output parsing for content generation less fragile.

## Scope

- define explicit output contract expectations for each high-value stage
- record parser assumptions near each agent or in shared models
- add a version field or contract note where useful

## Primary Files

- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/agents/`
- `src/cc_deep_research/content_gen/prompts/`
- `docs/content-generation.md`

## Acceptance Criteria

- core stages have an explicit parsing contract
- future prompt edits have a clear place to update matching parser assumptions

## Validation

- `uv run pytest tests/test_content_gen.py tests/test_iterative_loop.py -v`
