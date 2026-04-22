# P5-T2 - Split Content-Gen Store

## Outcome

Content-gen dashboard state is separated by feature.

## Scope

- Split pipeline state/actions.
- Split backlog state/actions.
- Split brief and revision state/actions.
- Split scripts, strategy, and publish queue state/actions.

## Implementation Notes

- Keep existing UI behavior while moving state.
- Use compatibility hooks temporarily if needed.
- Avoid one new mega-store replacing the old mega-store.

## Acceptance Criteria

- Components can subscribe to feature-specific state.
- The old `useContentGen` shape is removed or reduced to a transitional facade.
- Existing content-gen pages continue to work.

## Verification

- Run dashboard build and targeted content-gen e2e tests.
