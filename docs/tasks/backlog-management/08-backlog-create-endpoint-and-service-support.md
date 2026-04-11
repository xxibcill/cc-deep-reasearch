# Task 08: Add Backlog Create Endpoint And Service Support

Status: Done

Phase:
Phase 3 - Full CRUD Create Flow

Goal:
Extend the backend so operators can create backlog items through a first-class API instead of relying on generated items or manual YAML edits.

Primary files:
- `src/cc_deep_research/content_gen/backlog_service.py`
- `src/cc_deep_research/content_gen/storage/backlog_store.py`
- `src/cc_deep_research/content_gen/router.py`

Scope:
- Add a typed request model for backlog item creation.
- Add a `create_item()` or equivalent service helper that normalizes timestamps and defaults.
- Persist new items through the existing managed backlog store.
- Return the created item in API responses.
- Reject invalid input cleanly, especially missing core fields like `idea`.

Acceptance criteria:
- The backend exposes `POST /api/content-gen/backlog`.
- Created items receive stable IDs and timestamps.
- New items persist to disk and are returned with the same shape used by list and patch flows.

Validation:
- Manual API call or backend test-style invocation against a temp backlog path.

Out of scope:
- Dashboard create UI
- Bulk import
- Automatic idea generation
