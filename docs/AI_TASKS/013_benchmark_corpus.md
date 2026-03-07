# Task 013: Create A Benchmark Query Corpus

Status: Done

## Objective

Create a stable benchmark set that covers the main research modes and lets later workflow changes be measured against a fixed input set.

## Scope

- define a corpus covering:
  - simple factual queries
  - comparison queries
  - time-sensitive queries
  - evidence-heavy science or health queries
  - market or policy queries
- store the corpus in a versioned format suitable for test or script input
- document expected usage

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/docs/`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/`
- `/Users/jjae/Documents/guthib/cc-deep-research/README.md`

## Dependencies

None.

## Acceptance Criteria

- corpus format is stable and easy to load from scripts
- each benchmark case has a category and short rationale
- at least one time-sensitive case is marked as date-sensitive

## Suggested Verification

- add a small loader test if a parser or schema is introduced

## Completion Notes

- Completed on 2026-03-07
- Added a versioned benchmark corpus JSON at `/Users/jjae/Documents/guthib/cc-deep-research/docs/benchmark_corpus.json`
- Added typed loader utilities in `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/benchmark.py`
- Added loader validation tests in `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_benchmark.py`
- Revalidated with `uv run pytest tests/test_benchmark.py` and `uv run ruff check src/cc_deep_research/benchmark.py tests/test_benchmark.py src/cc_deep_research/__init__.py`
