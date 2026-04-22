# P4-T4 - Narrow Model Imports

## Outcome

Internal code imports models from narrower domain modules where practical.

## Scope

- Replace broad `from cc_deep_research.content_gen.models import ...` imports in internal modules where direct imports are clear.
- Keep public compatibility re-exports available.
- Avoid mass import churn that obscures behavior changes.
- Update tests only where imports move intentionally.

## Implementation Notes

- Do this after contract tests are in place.
- Prefer small batches by domain.
- Do not remove `models/__init__.py` compatibility exports in this task.

## Acceptance Criteria

- New internal code uses direct domain model imports.
- Existing public imports still work.
- Import changes do not alter runtime behavior.

## Verification

- Run import-related tests and a focused backend test subset.
