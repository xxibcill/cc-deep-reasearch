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
