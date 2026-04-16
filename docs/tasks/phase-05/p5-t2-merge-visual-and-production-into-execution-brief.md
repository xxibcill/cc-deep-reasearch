# P5-T2 - Merge Visual And Production Into Execution Brief

## Objective

Create one execution brief that covers beat-to-visual mapping, owners, assets, and shoot constraints when separate artifacts are unnecessary.

## Scope

- design an execution brief model that can replace separate visual and production outputs for most formats
- keep support for richer split outputs where a complex asset still needs them
- update docs and dashboard views to show the grouped execution contract

## Affected Areas

- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/agents/visual.py`
- `src/cc_deep_research/content_gen/agents/production.py`
- `docs/content-generation.md`

## Dependencies

- P5-T1 must define when the grouped execution brief is sufficient

## Acceptance Criteria

- the default operator handoff is one execution brief
- complex formats can still opt into deeper split planning
- execution ownership and required assets stay explicit
