# Phase 08 - Radar Workflow Conversion And Quality Loops

## Functional Feature Outcome

Radar opportunities can launch downstream workflows, collect explicit feedback, and emit enough telemetry and operator guidance to tune quality over time.

## Why This Phase Exists

Radar only becomes a core product surface if it drives action. Users must be able to move from opportunity to research or content execution without re-entering the same context. After that handoff works, the product needs feedback and analytics loops to improve ranking quality rather than becoming a stale inbox.

## Scope

- Convert opportunities into research runs and content-generation flows.
- Persist workflow linkage, status history, and user feedback.
- Expose telemetry and analytics needed for ranking and UX tuning.
- Add operator guidance for calibration and rollout.

## Tasks

| Task | Summary |
| --- | --- |
| [P8-T1](../tasks/phase-08/p8-t1-convert-radar-opportunities-into-research-runs.md) | Add the backend and UI bridge for launching research runs from Radar opportunities with prefilled context. |
| [P8-T2](../tasks/phase-08/p8-t2-convert-radar-opportunities-into-content-gen-flows.md) | Add the bridge for launching backlog, brief, and content-generation entry points from Radar opportunities. |
| [P8-T3](../tasks/phase-08/p8-t3-add-feedback-status-history-and-ranking-loop-inputs.md) | Persist status history and feedback signals so the engine can learn from user behavior. |
| [P8-T4](../tasks/phase-08/p8-t4-add-analytics-operator-playbook-and-calibration-tools.md) | Add telemetry views, operator documentation, and basic calibration tools for V1 rollout. |

## Dependencies

- Radar dashboard experience from Phase 07.
- Stable opportunity persistence and scoring behavior from Phases 05 and 06.
- Existing research and content-generation entry points.

## Exit Criteria

- Radar opportunities can launch at least one research flow and one content flow.
- Feedback actions persist and are visible in data and telemetry.
- Operators can inspect enough quality signals to tune the feature post-launch.
- Rollout guidance exists for testing and calibration.
