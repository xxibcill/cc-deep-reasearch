# P2-T2 - Add ROI And Fast-Fail Gates

## Status

Done.

Implemented:
- `IdeaScores` model gains `effort_tier` (EffortTier enum: quick/standard/deep) and `expected_upside` (1-5) fields
- `ScoringOutput` gains `effort_summary` dict mapping tier to count of ideas — provides fast visibility into pipeline effort distribution
- `ContentGenConfig` in schema.py gains `scoring_effort_tier_cap` setting (default: deep) — allows operators to cap the maximum effort tier the scorer will recommend
- `IdeaScores` gains `kill_reason` field to record why a kill recommendation was made (for debugging and audit)
- `score_ideas_user` prompt updated to ask scorer to declare effort tier and expected upside per idea
- `ContentGenConfig.scoring_min_upside_threshold` added (default: 2) — ideas below this upside are auto-killed unless overridden
- Tests added for effort tier field, upside threshold logic, and kill reason capture

## Objective

Prevent low-upside ideas from consuming research and drafting time by making effort and expected return part of the selection contract.

## Scope

- add expected upside, effort score, and research budget inputs to idea scoring
- define minimum thresholds and override rules for advancing an idea
- record kill reasons and reuse recommendations for rejected ideas

## Affected Areas

- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/config/schema.py`
- `src/cc_deep_research/content_gen/agents/backlog.py`
- `docs/content-gen-backlog.md`

## Dependencies

- P2-T1 must define the unified decision lane

## Acceptance Criteria

- ideas cannot enter research without a declared effort tier and expected upside
- fast-fail thresholds are documented and testable
- rejected ideas retain enough metadata to be reused later
