# P5-T1 - Split Content-Gen API Client

## Outcome

Content-gen frontend API calls are grouped by feature instead of one large client file.

## Scope

- Split pipeline API calls.
- Split backlog API calls.
- Split brief and revision API calls.
- Split scripts, strategy, publish, audit, and maintenance API calls.

## Implementation Notes

- Keep a shared Axios client and shared error handling.
- Preserve exported function names through compatibility barrels if needed.
- Avoid changing API paths.

## Acceptance Criteria

- `content-gen-api.ts` is reduced or becomes a compatibility barrel.
- Feature API modules are easy to scan.
- Existing imports either still work or are migrated cleanly.

## Verification

- Run TypeScript checks and dashboard tests that import content-gen API functions.
