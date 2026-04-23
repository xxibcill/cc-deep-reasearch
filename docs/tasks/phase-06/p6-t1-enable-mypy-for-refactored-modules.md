# P6-T1 - Enable Mypy For Refactored Modules

## Outcome

New and refactored backend modules are type-checked before the whole repo is ready.

## Scope

- Add mypy overrides for new pipeline and service modules.
- Keep global `ignore_errors` behavior only where legacy code still needs it.
- Fix typing issues introduced in refactored modules.
- Avoid broad whole-repo typing cleanup in this task.

## Implementation Notes

- Start with the smallest stable module set.
- Prefer typed protocols for injected dependencies.
- Keep tests compatible with stricter module typing.

## Acceptance Criteria

- Refactored modules are covered by stricter mypy behavior.
- Type checks pass for the enabled module set.
- Remaining unchecked areas are documented.

## Verification

- Run the selected mypy command and relevant backend tests.
