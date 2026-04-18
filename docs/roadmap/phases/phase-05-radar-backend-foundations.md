# Phase 05 - Radar Backend Foundations

## Functional Feature Outcome

The product can store and serve Radar sources, raw signals, opportunities, statuses, and scoring details through a stable backend contract.

## Why This Phase Exists

Radar will fail quickly if the team starts with UI or scoring experiments before the backend shape is stable. The dashboard needs stable data contracts. The ingestion pipeline needs durable storage. Workflow conversion needs traceable opportunity records. This phase creates the base package, persistence model, service layer, and route contracts that every later phase depends on.

## Scope

- Add a dedicated backend package for Radar domain models and services.
- Define persistent storage for sources, raw signals, opportunities, score breakdowns, feedback, and workflow links.
- Expose a stable API surface for listing opportunities, inspecting details, and mutating statuses.
- Wire Radar lifecycle events into the existing telemetry system.

## Tasks

| Task | Summary |
| --- | --- |
| [P5-T1](../tasks/phase-05/p5-t1-create-radar-domain-models-and-storage-contracts.md) | Create the Radar backend package, typed domain models, and persistence contracts for sources, signals, opportunities, scoring, and feedback. |
| [P5-T2](../tasks/phase-05/p5-t2-implement-radar-stores-and-service-layer.md) | Implement stores and service methods for creating, listing, updating, and linking Radar entities. |
| [P5-T3](../tasks/phase-05/p5-t3-add-radar-api-routes-telemetry-and-backend-tests.md) | Register Radar API routes, add telemetry emission, and add backend tests for the new contracts. |

## Dependencies

- The target product shape in [opportunity-radar-prd.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/opportunity-radar-prd.md).
- Familiarity with existing backend route and storage patterns in `web_server.py`, `content_gen/router.py`, and `content_gen/storage/`.

## Exit Criteria

- A new Radar backend package exists with typed models and service boundaries.
- Radar entities persist across process restarts.
- The backend exposes stable JSON contracts for sources and opportunities.
## Status: Done
