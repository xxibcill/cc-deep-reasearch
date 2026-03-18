# Task 002: Build Fixture Corpus And Replay Helpers

Status: Completed

## Objective

Create reusable, realistic fixture data and helper loaders so runtime-hardening tests can exercise real payload shapes without live provider calls.

## Scope

- add recorded fixture payloads for Tavily search responses and Claude analysis responses
- include both healthy and malformed variants for the same boundary when practical
- add helper utilities to load fixture JSON or markdown responses into tests
- keep fixture naming aligned with pipeline stages, not with one-off bug names

## Target Files

- `tests/fixtures/`
- `tests/helpers/`
- `tests/__init__.py`

## Dependencies

- [001_pipeline_failure_inventory.md](001_pipeline_failure_inventory.md)

## Acceptance Criteria

- tests can load realistic Tavily and Claude fixtures from shared helpers instead of inlining large payloads
- at least one fixture covers structured cross-reference points and one covers malformed or partial analysis output
- fixtures are deterministic and safe to commit

## Suggested Verification

- run targeted tests for the new fixture helpers
- confirm fixture files are small enough to inspect and large enough to represent real payload structure

