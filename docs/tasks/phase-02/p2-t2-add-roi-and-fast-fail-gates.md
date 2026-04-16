# P2-T2 - Add ROI And Fast-Fail Gates

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
