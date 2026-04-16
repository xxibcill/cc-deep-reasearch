# P3-T2 - Merge Angle Choice With Argument Design

## Objective

Replace the current linear angle-then-argument flow with a single thesis artifact that carries the chosen angle, core claim, and support structure together.

## Scope

- combine selected angle, thesis, support claims, objections, and narrative structure into one artifact
- keep the `ClaimLedger` linked at the same layer so evidence status is visible alongside argument design
- reduce handoff churn between angle generation and argument mapping

## Affected Areas

- `src/cc_deep_research/content_gen/agents/angle.py`
- `src/cc_deep_research/content_gen/agents/argument_map.py`
- `src/cc_deep_research/content_gen/models.py`
- `docs/content-generation.md`

## Dependencies

- P3-T1 must define research depth and evidence status inputs

## Acceptance Criteria

- the workflow produces one thesis artifact instead of separate angle and argument decisions
- evidence status is visible at the claim level during argument design
- drafting can start from one approved narrative contract
