# P4-T3 - Surface Operating Fitness And Risk Signals

## Summary

Turn strategy health and governance data into visible operating signals for the product.

## Scope

- Surface operating-fitness metrics, strategy drift indicators, and learning-bias warnings.
- Add dashboard views or panels for strategy risk and stale-rule visibility.
- Connect telemetry or query outputs where needed to support those views.

## Deliverables

- Strategy-risk and operating-fitness surfaces
- Backend query support for those signals
- Documentation for interpreting the signals

## Dependencies

- P4-T1 validation
- P4-T2 lifecycle metadata

## Acceptance Criteria

- Operators can see when strategy is decaying, stale, or biased.
- Operating-fitness signals are visible without inspecting raw storage files.

## Status

**Done**

Implemented:
- Extended `OperatingFitnessMetrics` with P4-T3 drift and bias fields: `rule_churn_rate`, `deprecated_rules_count`, `new_rules_count`, `avg_rule_confidence`, `rules_needing_review_count`, `hook_rule_count`, `framing_rule_count`, `scoring_rule_count`, `packaging_rule_count`, `other_rule_count`
- Computed properties: `rule_diversity_ratio`, `learning_bias_score`, `drift_summary`
- `ContentGenTelemetryStore._compute_drift_metrics()` derives strategy risk signals from rule version history: churn rate, deprecated/new rule counts, average confidence, review-needed count, and rule type distribution for bias detection
- `GET /api/content-gen/operating-fitness` endpoint (existing) now returns drift and bias data via `query_content_gen_operating_fitness()`
- Frontend `OperatingFitnessPanel` component showing kill rate, publish rate, cycle times, throughput, and drift summary including bias warnings
- TypeScript types: `OperatingFitnessMetrics` in `dashboard/src/types/content-gen.ts`
- API function: `getOperatingFitness()` in `dashboard/src/lib/content-gen-api.ts`
- Frontend `FitnessMetricRow` helper component
