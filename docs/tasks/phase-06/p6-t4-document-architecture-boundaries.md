# P6-T4 - Document Architecture Boundaries

## Outcome

Architecture documentation matches the refactored code structure.

## Scope

- Document content-gen pipeline ownership.
- Document route/service boundaries.
- Document model and storage contract strategy.
- Document dashboard state and API client ownership.

## Implementation Notes

- Update existing docs instead of creating duplicate architecture sources when possible.
- Keep docs tied to actual modules and entry points.
- Include migration notes for legacy compatibility paths.

## Acceptance Criteria

- New contributors can find the correct owner for each major workflow.
- Docs no longer describe removed legacy behavior as authoritative.
- Compatibility paths are clearly labeled.

## Verification

- Cross-check docs against current module names and public entry points.
