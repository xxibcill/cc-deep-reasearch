# P7-T2 - Feed Learnings Back Into Rules

## Objective

Turn performance review into actual rule updates for scoring, packaging, reuse, and time-budget decisions.

## Scope

- define which learnings update strategy memory, scoring rules, packaging heuristics, and reuse templates
- version rule changes so operators can see when guidance changed
- prevent ad hoc learnings from living only in free-form notes

## Affected Areas

- `src/cc_deep_research/content_gen/storage/strategy_store.py`
- `src/cc_deep_research/content_gen/models.py`
- `docs/content-generation.md`
- `docs/content-gen-workflow-template.md`

## Dependencies

- P7-T1 must provide reliable performance and throughput data

## Acceptance Criteria

- performance outputs can update next-run rules in a structured way
- rule changes are versioned and reviewable
- scoring and packaging behavior can be traced to observed results
