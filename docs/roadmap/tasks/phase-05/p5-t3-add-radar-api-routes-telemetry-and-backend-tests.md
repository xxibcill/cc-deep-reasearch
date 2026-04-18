# P5-T3 - Add Radar API Routes, Telemetry, And Backend Tests

## Status

Proposed.

## Summary

Expose Radar through the FastAPI backend and emit the telemetry needed for debugging and later analytics.

## Scope

- Add API request and response models for Radar.
- Register Radar routes in the dashboard backend.
- Emit telemetry for create, update, feedback, and conversion-adjacent operations where applicable.
- Add backend API tests for the initial route surface.

## Out Of Scope

- No dashboard components yet.
- No source scanning implementation yet.

## Read These Files First

- `src/cc_deep_research/web_server.py`
- `src/cc_deep_research/content_gen/router.py`
- `src/cc_deep_research/monitoring.py`
- `src/cc_deep_research/event_router.py`

## Suggested Files To Create Or Change

- `src/cc_deep_research/radar/router.py`
- `src/cc_deep_research/radar/api_models.py`
- `src/cc_deep_research/web_server.py`
- `tests/test_radar_api.py`

## Implementation Guide

1. Create request and response models first so the route contract is explicit.
2. Follow the existing router pattern used by content-gen routes rather than adding long route blocks directly into `web_server.py`.
3. Add only the core V1 route surface in this task:
   - `GET /api/radar/opportunities`
   - `GET /api/radar/opportunities/{id}`
   - `POST /api/radar/opportunities/{id}/status`
   - `POST /api/radar/opportunities/{id}/feedback`
   - `GET /api/radar/sources`
   - `POST /api/radar/sources`
4. Route handlers should call the service layer from P5-T2, not the stores.
5. Emit structured telemetry event names such as:
   - `radar.opportunity_status_updated`
   - `radar.feedback_recorded`
   - `radar.source_created`
6. Add API tests using FastAPI test clients and temporary directories or temporary app state.

## Guardrails For A Small Agent

- Do not put service logic inside route functions.
- Do not return ad-hoc dict shapes that bypass the typed response models.
- Keep error handling simple and consistent with the rest of the app.

## Deliverables

- Radar route module
- Route request and response models
- Telemetry hooks for core Radar actions
- API tests

## Dependencies

- P5-T1 domain models
- P5-T2 stores and service layer

## Verification

- Run `uv run pytest tests/test_radar_api.py -v`
- Manually inspect the new route registrations in `web_server.py`

## Acceptance Criteria

- The backend exposes a stable Radar API for frontend work.
- Core Radar mutations are emitted as telemetry events.
- Route tests cover at least one happy path and one error path per major endpoint.
