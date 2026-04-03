# Task 07: Add Regression Tests and Fixture Coverage (Partially Implemented)

## Status

Current status: Partially implemented

Implemented today:

- `tests/test_content_gen.py` covers `OpportunityBrief`, pipeline stage traces, skipped-stage behavior, and malformed backlog/scoring parsing.
- There are tests for the new planning-stage order and backlog prompt usage of `OpportunityBrief`.

Remaining gaps:

- There are no router/API tests proving live per-stage event emission.
- There are no shortlist-selection regression tests because shortlist selection has not been implemented yet.
- The fixture-backed smoke-path coverage described here is still missing.

## Goal

Add enough test coverage to make the upgraded pipeline safe to iterate on.

## Why

The planned changes introduce new contracts:

- new planning stage
- stage traces
- richer live events
- shortlist selection
- stricter early-stage validation

These need fixture-backed tests so future edits do not break them silently.

## Scope

In scope:

- content-gen model tests
- orchestrator tests
- router event tests
- malformed-output tests
- fixture-backed pipeline smoke path where practical

Out of scope:

- end-to-end browser test expansion unless needed for changed payloads

## Suggested File Targets

- `tests/test_content_gen.py`
- router or web-server tests that cover content-gen APIs
- test fixtures under `tests/helpers/` or nearby existing fixture locations

## Acceptance Criteria

- new models have serialization tests
- orchestrator behavior is covered for stage ordering and selection logic
- router tests cover live stage events
- malformed-output cases are asserted explicitly

## Suggested Test Cases

- `OpportunityBrief` is created and stored
- stage traces are appended in order
- stage completion is emitted live
- shortlist selection does not depend on list order
- malformed backlog output fails loudly
- skipped stages are represented clearly

## Notes For Small Agent

Prefer narrow, deterministic tests with fake agents over broad integration tests.
