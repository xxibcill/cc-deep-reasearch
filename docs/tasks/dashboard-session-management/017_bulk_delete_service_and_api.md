# Task 017: Add Bulk Delete Service And API

Status: Done

## Objective

Implement backend bulk delete behavior on top of the shared purge service so operators can clean up many historical sessions without repeating single-delete requests.

## Scope

- add a bulk delete route that accepts multiple session ids under the new contract
- reuse the shared purge logic per session instead of duplicating deletion branches in the route handler
- make per-session failures isolated so one bad artifact does not abort the entire batch
- return an aggregate summary suitable for review dialogs and post-action toasts

## Target Files

- `src/cc_deep_research/research_runs/session_purge.py`
- `src/cc_deep_research/web_server.py`
- `src/cc_deep_research/research_runs/models.py`
- `tests/test_web_server.py`

## Dependencies

- [016_bulk_session_action_contract.md](016_bulk_session_action_contract.md)

## Acceptance Criteria

- multiple historical sessions can be deleted in one request
- active conflicts and missing sessions remain visible as per-session results
- the route and service stay idempotent enough for retry after partial cleanup

## Suggested Verification

- run `uv run pytest tests/test_web_server.py tests/test_session_store.py`
