# P1-T3 - Split Strategy From Run Constraints

## Objective

Separate evergreen strategy memory from per-run constraints so operators can reuse the brand system without carrying stale campaign decisions into every run.

## Scope

- keep long-lived positioning, tone, proof standards, and audience rules in strategy memory
- move content type, effort tier, owner, channel goal, and current success target into the run brief
- update managed briefs and CLI inputs so the split is operational, not just documented

## Affected Areas

- `src/cc_deep_research/content_gen/storage/strategy_store.py`
- `src/cc_deep_research/content_gen/brief_service.py`
- `src/cc_deep_research/content_gen/cli.py`
- `docs/brief-management.md`

## Dependencies

- P1-T2 must define the policy fields that belong in a run brief

## Acceptance Criteria

- strategy memory contains reusable constraints only
- run briefs capture the variables that change per content cycle
- operators can set content type and effort tier before opportunity scoring
