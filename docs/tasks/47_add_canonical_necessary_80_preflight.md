# Task 47: Add One Canonical Local "Necessary 80%" Preflight

## Goal

Give contributors one command sequence that covers the maintenance-critical checks before merging.

## Scope

- combine the Python preflight, dashboard build, and essential dashboard smoke tests into one documented workflow
- keep it cheap enough for regular use

## Primary Files

- `docs/PREFLIGHT.md`
- optional helper script under `scripts/`

## Acceptance Criteria

- contributors have one obvious maintenance-focused preflight path
- the commands avoid live API calls

## Validation

- run the documented command sequence locally
