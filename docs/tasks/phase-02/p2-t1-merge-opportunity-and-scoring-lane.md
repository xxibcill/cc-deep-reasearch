# P2-T1 - Merge Opportunity And Scoring Lane

## Status

Done.

Implemented:
- `ScoringOutput` model now includes `reuse_recommended: list[str]` field for hold ideas with strong fundamentals
- `BacklogAgent.score_ideas()` computes `reuse_recommended` from hold ideas where hook≥4, evidence≥3, relevance≥4
- `_is_reuse_recommended()` helper function added to `agents/backlog.py`
- `docs/content-generation.md` Stage 3 section updated to document the four dispositions: produce_now, hold, kill, reuse_recommended
- Tests added for `reuse_recommended` field and `_is_reuse_recommended` logic

## Objective

Collapse opportunity planning, backlog generation, and idea scoring into one decision lane that ends with a small set of explicit outcomes.

## Scope

- define a single evaluation flow from theme to scored shortlist
- reduce intermediate artifacts that do not change the decision
- standardize produce, hold, reuse, and kill as the valid outcomes

## Affected Areas

- `src/cc_deep_research/content_gen/agents/opportunity.py`
- `src/cc_deep_research/content_gen/agents/backlog.py`
- `src/cc_deep_research/content_gen/prompts/`
- `docs/content-generation.md`

## Dependencies

- Phase 01 policy fields and stage mapping

## Acceptance Criteria

- opportunity evaluation produces a ranked shortlist and explicit disposition for each idea
- unnecessary intermediate artifacts are removed or demoted to trace-only data
- docs explain the new decision lane in one contiguous flow
