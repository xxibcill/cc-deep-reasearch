# Phase 07 - Radar Dashboard Experience

## Functional Feature Outcome

Operators can open a dedicated Radar workspace in the dashboard, review prioritized opportunities, inspect evidence, and manage source configuration.

## Why This Phase Exists

Radar is meant to become a decision surface, not an internal backend feature. The dashboard must make the feature feel curated, actionable, and low-noise. This phase turns backend contracts into an operator-ready experience while staying aligned with the dashboard's current routing, API, and component patterns.

## Scope

- Add Radar navigation and TypeScript contracts.
- Build the Radar list page and opportunity detail surface.
- Add source management UI and truthful empty/loading/error states.
- Cover the critical UX paths with Playwright tests.

## Tasks

| Task | Summary |
| --- | --- |
| [P7-T1](../tasks/phase-07/p7-t1-add-radar-types-api-client-and-navigation.md) | Add TypeScript types, API helpers, dashboard routing, and navigation entries for Radar. |
| [P7-T2](../tasks/phase-07/p7-t2-build-radar-inbox-and-opportunity-detail-ui.md) | Build the Radar inbox and detail UI using the new backend contracts. |
| [P7-T3](../tasks/phase-07/p7-t3-build-source-management-empty-states-and-dashboard-tests.md) | Add source management, empty/loading/error states, and Playwright coverage for the main Radar flows. |

## Dependencies

- Stable backend API from Phase 05.
- Usable opportunity data and score explanations from Phase 06.

## Exit Criteria

- The dashboard has a first-class `Radar` route.
- Users can list, filter, inspect, and update opportunities.
- Users can manage initial monitored sources from the UI.
- Playwright coverage exists for the main Radar flows.
