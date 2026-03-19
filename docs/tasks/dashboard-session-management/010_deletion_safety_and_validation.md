# Task 010: Add Deletion Safety, Regression Coverage, And Docs

Status: Done

## Objective

Lock down the feature with tests and user-facing documentation so direct dashboard deletion remains safe and predictable.

## Scope

- add backend regression coverage for full, partial, missing, and active-session delete cases
- add frontend validation coverage for list removal and session-page redirect flows where practical
- document the new dashboard capability and any remaining limitations such as no bulk delete
- document exact destructive scope so users know what history will be removed

## Target Files

- `tests/test_web_server.py`
- `tests/test_session_store.py`
- `docs/DASHBOARD_GUIDE.md`
- `docs/USAGE.md`

## Dependencies

- [006_delete_session_api.md](006_delete_session_api.md)
- [008_session_list_delete_action.md](008_session_list_delete_action.md)
- [009_session_page_delete_flow.md](009_session_page_delete_flow.md)

## Acceptance Criteria

- destructive behavior is covered by focused regression tests
- dashboard and CLI docs explain how browser-driven deletion works
- contributors can verify the feature without manually inspecting filesystem leftovers

## Suggested Verification

- run targeted `uv run pytest`
- run `npm run lint` in `dashboard`
