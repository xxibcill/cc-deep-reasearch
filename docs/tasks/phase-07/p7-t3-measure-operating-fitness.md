# P7-T3 - Measure Operating Fitness

## Objective

Prove that the redesigned workflow is faster and more practical by tracking operating fitness, not just content outcomes.

## Scope

- define metrics for cycle time, kill rate, reuse rate, cost control, and throughput
- add reporting that compares the old and new operating model over time
- make operating fitness part of the success criteria for the workflow redesign

## Affected Areas

- `src/cc_deep_research/telemetry/query.py`
- `docs/TELEMETRY.md`
- `docs/CONTENT_GEN_IMPROVEMENT_PLAN.md`
- `docs/content-generation.md`

## Dependencies

- P7-T1 and P7-T2 must provide stable measurement inputs

## Acceptance Criteria

- the team can quantify whether the workflow got faster and cheaper
- kill rate and reuse rate are visible alongside publish metrics
- the redesign is evaluated against operating fitness, not completeness alone
