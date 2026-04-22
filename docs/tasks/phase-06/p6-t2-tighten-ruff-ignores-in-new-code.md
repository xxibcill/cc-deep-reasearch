# P6-T2 - Tighten Ruff Ignores In New Code

## Outcome

New backend code follows stricter lint expectations than legacy code.

## Scope

- Identify ignores that should not apply to new modules.
- Add per-file or per-package lint configuration where appropriate.
- Fix lint issues in refactored modules.
- Leave unrelated legacy lint debt alone.

## Implementation Notes

- Do not make sweeping style-only rewrites.
- Keep lint changes scoped to refactored boundaries.
- Prefer local improvements over global rule changes unless CI can absorb them.

## Acceptance Criteria

- New modules pass the selected stricter lint rules.
- Existing legacy ignores are not expanded unnecessarily.
- Lint configuration intent is documented.

## Verification

- Run `uv run ruff check` for the affected paths.
