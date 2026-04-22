# P6-T5 - Create Refactor Regression Checklist

## Outcome

Future changes have a concise checklist for protecting the refactored boundaries.

## Scope

- List backend checks by affected boundary.
- List dashboard checks by affected feature.
- List contract fixture update rules.
- List when to run broader e2e coverage.

## Implementation Notes

- Keep the checklist short enough that engineers will use it.
- Include commands where stable.
- Include guidance for documenting blocked checks.

## Acceptance Criteria

- The checklist covers pipeline, routes, contracts, and dashboard state.
- The checklist is referenced from architecture or contributor docs.
- Future refactor tasks can cite it as a verification baseline.

## Verification

- Dry-run the checklist against one completed phase and adjust gaps.
