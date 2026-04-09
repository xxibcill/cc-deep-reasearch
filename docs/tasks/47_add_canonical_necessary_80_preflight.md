# Task 47: Add One Canonical Local "Necessary 80%" Preflight

## Status

- [x] Done - made `./scripts/preflight` the canonical maintenance preflight, aligned it with the mocked dashboard smoke alias, documented the one-command workflow in `docs/PREFLIGHT.md`, and validated the full sequence locally without live API calls.

## Goal

Give contributors one command sequence that covers the maintenance-critical checks before merging.

## Scope

- combine the Python preflight, dashboard build, and essential dashboard smoke tests into one documented workflow
- keep it cheap enough for regular use

## Primary Files

- `docs/PREFLIGHT.md`
- `scripts/preflight`

## Acceptance Criteria

- [x] contributors have one obvious maintenance-focused preflight path
- [x] the commands avoid live API calls

## Validation

- [x] run the documented command sequence locally
