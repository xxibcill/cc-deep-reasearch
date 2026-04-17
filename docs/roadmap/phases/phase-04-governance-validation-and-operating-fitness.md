# Phase 04 - Governance, Validation, And Operating Fitness

## Functional Feature Outcome

The strategy system can detect weak or stale strategy states, govern rule promotion and retirement, and surface operating fitness signals that keep the outer layer trustworthy over time.

## Why This Phase Exists

Without governance, a richer strategy layer will slowly degrade into noisy configuration and stale rules. The guide already identifies missing readiness gates, missing promotion criteria, and empty operating-fitness signals. This phase hardens the system so operators can trust that strategy quality remains high as learnings accumulate and platform conditions change.

## Scope

- Add validation rules for blocking and warning-level strategy states.
- Introduce rule promotion, review, expiry, and retirement mechanics.
- Surface strategy readiness, drift, and operating-fitness signals in API and dashboard views.
- Ensure publishing and promotion workflows can check required strategy health before proceeding.

## Tasks

| Task | Summary |
| --- | --- |
| [P4-T1](../tasks/phase-04/p4-t1-add-strategy-readiness-validation.md) | Add validation and readiness reporting for strategy completeness and quality. |
| [P4-T2](../tasks/phase-04/p4-t2-add-rule-governance-lifecycle.md) | Add promotion, expiry, review, and deprecation mechanics for reusable rules. |
| [P4-T3](../tasks/phase-04/p4-t3-surface-operating-fitness-and-risk-signals.md) | Surface operating-fitness, drift, and strategy-risk signals in the product. |

## Dependencies

- Earlier phases must establish the richer schema, editor, and learning records.
- Governance thresholds should be calibrated against real operator usage instead of guessed entirely upfront.

## Exit Criteria

- The system can reject invalid strategy states and warn on weak but technically valid ones.
- Reusable rules carry lifecycle metadata and can be reviewed or deprecated explicitly.
- Operators can see strategy readiness and drift in the dashboard.
- Publishing and promotion flows can consult strategy health before high-impact actions.
