# Task 40: Create a Python Preflight CI Workflow

## Goal

Automate the existing preflight checks so reliability does not depend on manual memory.

## Scope

- add a GitHub Actions workflow for Python tests and static checks
- run the preflight subsets from `docs/PREFLIGHT.md`
- keep runtime reasonable by using fixture-backed suites only

## Primary Files

- `.github/workflows/`
- `docs/PREFLIGHT.md`

## Acceptance Criteria

- CI runs on pull requests and pushes
- core Python preflight checks are automated

## Status

- [x] Done - added `preflight.yml` GitHub Actions workflow matching `docs/PREFLIGHT.md`, validated with 275 tests passing

## Validation

- confirm workflow YAML is valid
- if local tools exist, run the same commands locally before finishing
