# P5-T3 - Extract Large Component Actions

## Outcome

Large dashboard components delegate mutation and loading logic to focused hooks.

## Scope

- Extract backlog page/panel action logic.
- Extract brief detail action logic.
- Extract pipeline action logic.
- Keep presentational component behavior stable.

## Implementation Notes

- Separate view rendering from mutation orchestration.
- Keep loading, busy, and error state close to the feature hook.
- Avoid visual redesign during this task.

## Acceptance Criteria

- Large components are smaller and easier to scan.
- Action hooks are testable independently.
- UI behavior remains unchanged.

## Verification

- Run dashboard build and targeted Playwright workflows.
