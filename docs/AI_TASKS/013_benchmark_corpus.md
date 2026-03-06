# Task 013: Create A Benchmark Query Corpus

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
