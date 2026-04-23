# P3-T2 - Extract Session Routes

## Outcome

Session-related API behavior is grouped into dedicated route modules.

## Scope

- Move session list and detail routes.
- Move delete, bulk delete, purge, archive, and restore routes.
- Move events, report, bundle, artifacts, checkpoints, resume, and rerun-step routes.
- Preserve query parameters and response payloads.

## Implementation Notes

- Split into multiple modules if one session router becomes too large.
- Reuse existing helper functions by moving them with the route group they serve.
- Keep session store behavior unchanged.

## Acceptance Criteria

- Session routes are no longer embedded in `web_server.py`.
- Existing session API tests pass.
- Dashboard session pages continue to load.

## Verification

- Run session route tests and dashboard session smoke tests.
