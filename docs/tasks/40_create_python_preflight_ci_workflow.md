# Task 40: Create a Python Preflight CI Workflow

## Goal

Automate the existing preflight checks so reliability does not depend on manual memory.

## Scope

- add a GitHub Actions workflow for Python tests and static checks
- run the preflight subsets from `docs/PREFLIGHT.md`
- keep runtime reasonable by using fixture-backed suites only

## Primary Files

- `.github/workflows/preflight.yml` - added lint and type check steps
- `scripts/preflight` - added ruff check and mypy to python preflight

## Acceptance Criteria

- CI runs on pull requests and pushes
- core Python preflight checks are automated

## Status

- [x] Done - added `preflight.yml` GitHub Actions workflow with lint + type check + pytest subsets, updated `scripts/preflight` to match. Validation: 275 tests passing (1 pre-existing failure unrelated to scope)

## Validation

- confirm workflow YAML is valid
- if local tools exist, run the same commands locally before finishing
