# P6-T3 - Remove Unused Legacy Content-Gen Paths

## Outcome

Unused legacy content-gen code is removed or quarantined after compatibility is proven.

## Scope

- Measure imports and runtime references to legacy content-gen paths.
- Remove dead helpers and dispatch code.
- Keep required compatibility shims.
- Update docs and tests for removed paths.

## Implementation Notes

- Do not remove compatibility code without contract and import evidence.
- Prefer deletion over keeping confusing dead code.
- If code cannot be removed yet, mark the owner and removal condition.

## Acceptance Criteria

- Normal content-gen execution has no legacy path dependency.
- Removed code has no active import references.
- Remaining legacy code has documented purpose.

## Verification

- Run import checks, content-gen tests, and route tests.
