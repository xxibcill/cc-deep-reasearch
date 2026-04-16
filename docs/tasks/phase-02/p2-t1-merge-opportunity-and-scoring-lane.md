# P2-T1 - Merge Opportunity And Scoring Lane

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
