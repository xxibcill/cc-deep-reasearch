# Task 004: Add Provider Response Replay Tests

Status: Completed

## Objective

Replay realistic provider responses at the search boundary so collection-stage parsing failures are caught without using live API credits.

## Scope

- add fixture-backed replay tests for Tavily response parsing
- cover empty results, partial metadata, and degraded but still valid results
- add explicit tests for provider-side error payloads that should map to typed exceptions
- keep live network access out of the test path

## Target Files

- `tests/test_tavily_provider.py`
- `tests/test_providers.py`
- `src/cc_deep_research/providers/tavily.py`

## Dependencies

- [002_fixture_corpus_and_helpers.md](002_fixture_corpus_and_helpers.md)

## Acceptance Criteria

- provider parsing logic is exercised with recorded response bodies instead of handcrafted tiny dicts alone
- typed exceptions for auth, rate limit, and network-like failures remain covered
- search result normalization is verified against realistic metadata fields

## Suggested Verification

- run `uv run pytest tests/test_tavily_provider.py tests/test_providers.py`

