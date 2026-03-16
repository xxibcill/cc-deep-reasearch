# Task 002: Clean Generated Artifacts

Status: Done

## Objective

Remove generated and install-time artifacts from the tracked source layout so refactor work happens against source code only.

## Scope

- verify ignore rules for `__pycache__/` and `dashboard/node_modules/`
- keep repository-visible source files separate from local build output
- do not delete user work or unrelated untracked files without confirmation

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/.gitignore`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/`

## Dependencies

None.

## Acceptance Criteria

- generated artifacts are ignored consistently
- repository navigation no longer includes dependency trees as source noise
- future diffs stay focused on refactor changes

## Suggested Verification

- run `git status --short`
- run `git ls-files | rg '(__pycache__|node_modules)'`
