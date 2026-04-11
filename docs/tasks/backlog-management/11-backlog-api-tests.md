# Task 11: Add Backlog API Tests

Status: Planned

Phase:
Phase 4 - Hardening And Rollout

Goal:
Protect backlog-management behavior at the API layer with focused tests for list and CRUD flows.

Primary files:
- `tests/test_web_server.py`
- `tests/test_content_gen.py`

Scope:
- Add coverage for backlog list responses.
- Add route-level tests for create, patch, select, archive, and delete.
- Verify path metadata and item serialization where relevant.
- Verify failure behavior for unknown IDs and invalid create input.
- Prefer temp-path-backed tests so persistence behavior is real.

Acceptance criteria:
- API tests cover both happy-path and key failure cases.
- Tests verify that mutations persist through the managed backlog store.
- Future route regressions would fail fast in CI.

Validation:
- Run the relevant backend test targets for content-gen and web-server backlog flows.

Out of scope:
- Dashboard UI tests
- Visual regression coverage
