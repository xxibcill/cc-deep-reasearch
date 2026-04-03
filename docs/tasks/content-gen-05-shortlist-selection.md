# Task 05: Replace First-Winner Selection With Shortlist Logic (Done)

## Status

Current status: Done

Implemented today:

- `ScoringOutput` now carries `shortlist`, `selected_idea_id`, `selection_reasoning`, and `runner_up_idea_ids`.
- `PipelineContext` now stores the explicit idea selection state so downstream stages do not depend on list position.
- The scoring prompt and parser now support shortlist ranking plus deterministic fallback selection.
- Downstream orchestrator stages resolve the chosen idea explicitly instead of reading `produce_now[0]`.
- Regression tests now cover shortlist serialization, explicit selected-idea precedence, and downstream angle/research selection.

## Goal

Upgrade idea selection from first-match behavior to explicit shortlist ranking.

## Why

The current pipeline takes the first `produce_now` idea. That is simple, but too narrow and not explainable enough.

## Scope

In scope:

- extend scoring output with shortlist ordering
- preserve alternates in pipeline context
- record why the chosen idea won
- use chosen idea consistently for angle generation and downstream stages

Out of scope:

- UI review workflow for manual pickers
- post-publish learning loops

## Suggested File Targets

- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/agents/backlog.py`
- `src/cc_deep_research/content_gen/prompts/backlog.py`
- `src/cc_deep_research/content_gen/orchestrator.py`
- `tests/test_content_gen.py`
- `docs/content-generation.md`

## Suggested Additions

Possible fields:

- `shortlist`
- `selected_idea_id`
- `selection_reasoning`
- `runner_up_idea_ids`

## Acceptance Criteria

- scoring output can represent a ranked shortlist
- pipeline stores the chosen idea explicitly
- selection reasoning is preserved
- downstream stages no longer rely on `produce_now[0]`

## Testing

Add tests for:

- shortlist serialization
- explicit chosen idea wins over list order
- downstream angle and research stages read the chosen idea correctly

## Notes For Small Agent

Keep the initial selection rule deterministic. Do not add human-in-the-loop picking yet.
