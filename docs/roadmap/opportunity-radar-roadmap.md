# Opportunity Radar Roadmap

This roadmap breaks the `Opportunity Radar` PRD into implementation phases that are small enough for lower-context agents to execute safely.

## How To Use This Roadmap

Small agents should follow these rules before starting any task:

1. Read the task doc fully before touching code.
2. Read the "Read These Files First" section and inspect those files before making a plan.
3. Do not invent a parallel architecture if an existing storage, router, or dashboard pattern already fits.
4. Keep each task isolated. Do not opportunistically combine multiple tasks in one branch.
5. Add or update tests in the same task when the task doc says to do so.
6. Prefer extending existing API and dashboard conventions over creating one-off helpers.
7. If a required file or pattern does not exist, create the smallest compatible version and document it in the task result.

## Recommended Build Order

Do not start frontend work until the backend contracts from Phase 05 are stable.

Do not start scoring calibration or workflow conversion until opportunity persistence and ranking output are usable end-to-end.

When in doubt, build in this order:

1. domain models and storage
2. services and routes
3. source ingestion and scoring
4. dashboard experience
5. workflow conversion
6. feedback, analytics, and calibration

## Phases

| Phase | Outcome |
| --- | --- |
| [Phase 05 - Radar Backend Foundations](./phases/phase-05-radar-backend-foundations.md) | The backend can persist, query, and serve Radar sources, signals, opportunities, and scoring details through stable contracts. |
| [Phase 06 - Radar Ingestion And Opportunity Engine](./phases/phase-06-radar-ingestion-and-opportunity-engine.md) | The system can scan sources, normalize signals, cluster opportunities, and rank them with explainable scoring. |
| [Phase 07 - Radar Dashboard Experience](./phases/phase-07-radar-dashboard-experience.md) | Operators can use Radar from the dashboard to scan, inspect, and manage opportunities and sources. |
| [Phase 08 - Radar Workflow Conversion And Quality Loops](./phases/phase-08-radar-workflow-conversion-and-quality-loops.md) | Radar opportunities can launch downstream workflows, collect feedback, and produce the telemetry needed for quality tuning. |

## Sequencing Notes

- Phase 05 must land before any meaningful frontend implementation because the dashboard needs stable response types.
- Phase 06 should stay narrow on source coverage. The goal is usable ranking quality, not maximum connector count.
- Phase 07 should preserve the existing dashboard visual language and routing patterns.
- Phase 08 should focus first on research and content handoff quality, then on analytics polish.
