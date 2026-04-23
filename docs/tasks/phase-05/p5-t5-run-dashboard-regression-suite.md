# P5-T5 - Run Dashboard Regression Suite

## Outcome

Dashboard refactors are validated against build, lint, and critical workflows.

## Scope

- Run dashboard build.
- Run dashboard lint.
- Run targeted Playwright workflows for content-gen, backlog, briefs, and telemetry.
- Record any known remaining failures.

## Implementation Notes

- Use targeted tests first, then broader tests if runtime allows.
- Document blocked checks with the exact blocker.
- Do not hide failures by loosening tests.

## Acceptance Criteria

- Dashboard checks are green or documented with known blockers.
- Critical content-gen workflows still pass.
- Backend/frontend contract assumptions remain aligned.

## Verification

- Re-run the selected dashboard commands after final frontend changes.
