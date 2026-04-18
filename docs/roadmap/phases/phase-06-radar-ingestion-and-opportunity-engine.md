# Phase 06 - Radar Ingestion And Opportunity Engine

## Functional Feature Outcome

The system can ingest source items, normalize them into raw signals, cluster those signals into opportunities, and rank them with explainable scoring.

## Why This Phase Exists

Backend persistence alone does not create value. Radar becomes useful only when it can continuously turn noisy inputs into a short list of credible opportunities. This phase builds the first useful version of that engine while keeping source coverage intentionally narrow and explainability high.

## Scope

- Implement source scanning for a narrow initial set of source types.
- Normalize and deduplicate raw source items.
- Upsert opportunities from grouped signals.
- Add score breakdowns, explanations, and freshness handling.

## Tasks

| Task | Summary |
| --- | --- |
| [P6-T1](../tasks/phase-06/p6-t1-implement-source-scanning-entry-points.md) | Implement source configuration rules and scanning entry points for the first supported source types. |
| [P6-T2](../tasks/phase-06/p6-t2-normalize-dedupe-and-cluster-signals.md) | Normalize fetched items into raw signals, deduplicate repeats, and cluster related signals into opportunities. |
| [P6-T3](../tasks/phase-06/p6-t3-add-scoring-explanations-and-freshness-lifecycle.md) | Add scoring, priority labels, ranking explanations, freshness decay, and engine-level tests. |

## Dependencies

- Phase 05 storage and service contracts.
- A stable opportunity schema that can store score breakdowns and signal links.

## Exit Criteria

- At least one end-to-end scan path produces stored opportunities.
- Duplicate raw items do not create duplicate opportunities by default.
- Opportunities contain score details and human-readable explanations.
- Freshness and rescore behavior are covered by tests.
