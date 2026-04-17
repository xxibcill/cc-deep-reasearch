# P1-T2 - Add Migration And Storage Compatibility

## Status

Done. Added `_deep_merge` helper and updated `StrategyStore.update()` to use deep merging instead of shallow `model_copy`. Backward-compat tests added for old YAML shapes (string content_pillars) and nested object partial updates.

## Summary

Make richer strategy storage safe to adopt without breaking existing strategy YAML files or shallow update workflows.

## Scope

- Add load-time coercion for older strategy file shapes.
- Improve storage update behavior for nested objects so updates do not accidentally erase unrelated sections.
- Document compatibility expectations for `strategy.yaml`.

## Deliverables

- Updated `StrategyStore` behavior
- Backward-compatibility tests for old and new strategy shapes
- Documentation for migration behavior and expected file structure

## Dependencies

- P1-T1 schema definitions

## Acceptance Criteria

- Existing strategy files still load successfully.
- Nested strategy sections can be updated without unsafe partial overwrites.
- Storage behavior is covered by regression tests.
