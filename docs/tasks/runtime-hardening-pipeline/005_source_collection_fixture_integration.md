# Task 005: Add Source Collection Fixture Integration Tests

Status: Planned

## Objective

Exercise the real source-collection layer with fixture-backed providers so failures in merging, hydration, and provenance handling are caught before analysis begins.

## Scope

- test source collection using real collection services with fixture-backed provider doubles
- cover query-family provenance propagation, deduplication, and content hydration expectations
- verify degraded provider availability paths still produce stable session metadata
- avoid mocking away the collection logic under test

## Target Files

- `tests/test_orchestrator.py`
- `tests/test_providers.py`
- `src/cc_deep_research/orchestration/source_collection.py`
- `src/cc_deep_research/aggregation.py`

## Dependencies

- [002_fixture_corpus_and_helpers.md](002_fixture_corpus_and_helpers.md)
- [004_provider_response_replay_tests.md](004_provider_response_replay_tests.md)

## Acceptance Criteria

- at least one test runs the real source collection path with replayed provider payloads
- source provenance, deduplication, and provider degradation metadata are asserted together
- the test would fail if collection returns structurally invalid `SearchResultItem` data

## Suggested Verification

- run targeted `uv run pytest` coverage for source collection and orchestrator collection paths

