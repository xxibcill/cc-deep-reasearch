# Task 02: Align Backlog API Contract And Dashboard Types

Status: Done

Phase:
Phase 1 - Backlog Visibility

Goal:
Bring the dashboard backlog types in line with the Python models and the existing backlog API response shape before new UI behavior is added.

Primary files:
- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/router.py`
- `dashboard/src/types/content-gen.ts`

Scope:
- Audit the backlog item and backlog response shapes exposed by the backend.
- Update dashboard types for fields currently missing from `BacklogItem`.
- Add any missing status values such as `runner_up`.
- Add a typed backlog list response if the client benefits from preserving `path` metadata explicitly.
- Keep names consistent across backend and frontend to avoid adapter drift.

Acceptance criteria:
- Dashboard types cover all persisted backlog item fields needed by the feature.
- The frontend can represent the list response from `GET /api/content-gen/backlog` without `unknown` fields or silent drops.
- Status unions support all server-emitted backlog states used by the service.

Validation:
- Type-check the dashboard after updating the backlog types.

Out of scope:
- Store wiring
- Dedicated backlog page layout
- Create support
