# P2-T4 - Extract Strategy Scripting Maintenance Services

## Outcome

Remaining content-gen route domains are split into focused services.

## Scope

- Extract strategy endpoints.
- Extract scripting endpoints and saved script mutations.
- Extract publish queue and audit endpoints.
- Extract maintenance proposal and job endpoints.

## Implementation Notes

- Keep long-running or provider-dependent operations injectable.
- Keep timeout and route-level HTTP behavior in the route layer.
- Avoid mixing unrelated service concerns to recreate the router monolith.

## Acceptance Criteria

- Each remaining content-gen route group has a clear service owner.
- Service tests cover success and common failure paths.
- Route handlers stay small and readable.

## Verification

- Run content-gen route tests and any new service tests.
