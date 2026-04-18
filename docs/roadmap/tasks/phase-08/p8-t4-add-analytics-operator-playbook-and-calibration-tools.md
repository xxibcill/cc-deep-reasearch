# P8-T4 - Add Analytics, Operator Playbook, And Calibration Tools

## Status

Proposed.

## Summary

Add the minimum analytics, documentation, and operator controls needed to evaluate Radar quality after launch.

## Scope

- Emit and expose Radar telemetry and analytics counters.
- Add a lightweight operator playbook for rollout and tuning.
- Add one or two calibration controls if they fit the existing config model cleanly.

## Out Of Scope

- Full analytics warehouse work
- Broad enterprise observability tooling

## Read These Files First

- `docs/DASHBOARD_GUIDE.md`
- `docs/TELEMETRY.md`
- `src/cc_deep_research/telemetry/query.py`
- `dashboard/src/app/analytics/page.tsx`
- `dashboard/src/components/telemetry/`

## Suggested Files To Create Or Change

- `src/cc_deep_research/telemetry/query.py`
- `src/cc_deep_research/radar/router.py`
- `dashboard/src/app/analytics/page.tsx`
- `docs/DASHBOARD_GUIDE.md`
- `docs/opportunity-radar-prd.md`
- `docs/roadmap/opportunity-radar-roadmap.md`

## Implementation Guide

1. Add analytics queries or summaries for the core Radar metrics:
   - opportunity-to-action rate
   - dismissal rate
   - duplicate rate if possible
   - freshness latency
2. Expose these metrics either in the analytics page or a small Radar-specific summary surface.
3. If the existing config system can support it cleanly, add one or two safe tuning knobs such as:
   - minimum score threshold for `Act Now`
   - freshness decay window
4. Document a rollout checklist for operators:
   - how to seed sources
   - how to run manual scans
   - what signals to inspect after launch
   - how to interpret the new metrics

## Guardrails For A Small Agent

- Do not create a large configuration editor for every weighting dimension in V1.
- Prefer a documented playbook over a sprawling control surface.
- Make analytics honest. If a metric is approximate, say so in the UI or docs.

## Deliverables

- Radar quality metrics in telemetry or analytics surfaces
- Operator rollout and calibration guidance
- Optional safe config knobs for key thresholds

## Dependencies

- P8-T1 through P8-T3 so the system has real interactions to measure

## Verification

- Run the relevant backend tests for telemetry queries
- Run `cd dashboard && npm run lint`
- Manually confirm the docs explain how to evaluate Radar quality after rollout

## Acceptance Criteria

- Operators can inspect whether Radar is producing useful opportunities.
- The codebase contains practical rollout guidance for testing and calibration.
- Any added calibration controls are small, documented, and safe.
