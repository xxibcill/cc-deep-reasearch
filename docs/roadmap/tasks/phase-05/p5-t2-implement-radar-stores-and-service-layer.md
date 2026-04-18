# P5-T2 - Implement Radar Stores And Service Layer

## Status

Proposed.

## Summary

Implement storage and service methods for Radar entities so later tasks can create and query sources, opportunities, scores, feedback, and workflow links without duplicating persistence logic.

## Scope

- Add store classes or repository helpers for Radar entities.
- Add a service layer that centralizes the main Radar operations.
- Support create/list/update operations for sources and opportunities.
- Support linking scores, feedback, and workflows to opportunities.

## Out Of Scope

- No HTTP route wiring yet.
- No actual source scanning yet.
- No ranking algorithm yet.

## Read These Files First

- `src/cc_deep_research/content_gen/storage/backlog_store.py`
- `src/cc_deep_research/content_gen/storage/sqlite_backlog_store.py`
- `src/cc_deep_research/research_runs/service.py`
- `src/cc_deep_research/session_store.py`

## Suggested Files To Create Or Change

- `src/cc_deep_research/radar/stores.py`
- `src/cc_deep_research/radar/service.py`
- `src/cc_deep_research/radar/models.py`
- `tests/test_radar_stores.py`
- `tests/test_radar_service.py`

## Implementation Guide

1. Start with stores, not service methods.
2. Implement the smallest CRUD surface needed for later tasks:
   - create and list sources
   - save and list raw signals
   - create or update opportunities
   - save score breakdowns
   - append feedback history
   - append workflow links
3. After the stores exist, add a `RadarService` that wraps those operations behind methods that are meaningful to routes and the opportunity engine.
4. Keep one service method per clear action. Examples:
   - `list_opportunities`
   - `get_opportunity_detail`
   - `update_opportunity_status`
   - `record_feedback`
   - `link_workflow`
5. Return typed models from service methods instead of raw dictionaries.
6. Add tests that exercise the service methods through temporary directories so the persistence behavior is real.

## Guardrails For A Small Agent

- Do not let routes call store classes directly once the service exists.
- Do not duplicate save/load logic in multiple places.
- Do not mix future engine logic into the service layer yet.

## Deliverables

- Radar store implementation
- Radar service layer
- Store and service tests

## Dependencies

- P5-T1 domain models and persistence contracts

## Verification

- Run `uv run pytest tests/test_radar_stores.py tests/test_radar_service.py -v`
- Confirm service methods can create and read back stored entities from disk

## Acceptance Criteria

- Radar storage is reusable by routes and engine code.
- Store logic is isolated from HTTP and dashboard concerns.
- Service methods expose the core Radar backend actions with typed outputs.
