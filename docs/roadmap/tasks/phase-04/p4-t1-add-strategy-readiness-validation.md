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
