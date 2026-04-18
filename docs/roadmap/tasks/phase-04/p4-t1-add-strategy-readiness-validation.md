# P4-T1 - Add Strategy Readiness Validation

## Summary

Add explicit validation rules for strategy completeness and quality so weak strategy states are visible and, when necessary, blocked.

## Scope

- Implement blocking and warning checks from the strategy guide.
- Expose readiness status through backend APIs and dashboard state.
- Differentiate between invalid strategy, incomplete strategy, and healthy strategy.

## Deliverables

- Validation engine for strategy readiness
- API surface for readiness/warning output
- Dashboard consumption of readiness status

## Dependencies

- Phase 01 schema
- Phase 02 dashboard display hooks

## Acceptance Criteria

- The system can reject invalid strategy states and warn on weak ones.
- Operators can see which fields or ratios are causing readiness failures.

## Status

**Done**

Implemented:
- `StrategyReadiness` enum: `INVALID`, `INCOMPLETE`, `HEALTHY`
- `StrategyReadinessIssue` model with `code`, `label`, `severity` (`blocking`/`warning`), `field_path`, `detail`, `suggestion`
- `StrategyReadinessResult` model with `readiness`, `overall_score`, `issues`, `summary`, plus helper methods (`has_blockers()`, `is_healthy()`, `blocking_issues()`, `warning_issues()`)
- `StrategyStore.check_readiness()` running 9 checks: niche (blocking), content_pillars (blocking), expertise_edge, proof_standards, forbidden_claims, platforms, audience_segments, tone_rules, past_winners (all warning)
- `GET /api/content-gen/strategy/readiness` endpoint exposing validation results
- Frontend `ReadinessPanel` component in strategy workspace showing readiness level, completeness score, and per-issue cards with severity badges and suggestions
- TypeScript types: `StrategyReadiness`, `StrategyReadinessIssue`, `StrategyReadinessResult` in `dashboard/src/types/content-gen.ts`
- API functions: `getStrategyReadiness()` in `dashboard/src/lib/content-gen-api.ts`
