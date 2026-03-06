# Task 014: Build A Repeatable Benchmark Harness

## Objective

Add a scriptable harness that runs the workflow against the benchmark corpus and produces a comparable scorecard.

## Scope

- run the workflow with fixed configuration
- persist outputs for comparison across commits
- calculate scorecard metrics such as:
  - source count
  - unique domains
  - source-type diversity
  - iteration count
  - latency
  - validation score
- keep the harness usable in CI or local development

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/`
- `/Users/jjae/Documents/guthib/cc-deep-research/pyproject.toml`

## Dependencies

- [013_benchmark_corpus.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/013_benchmark_corpus.md)

## Acceptance Criteria

- the harness runs the whole corpus with one command
- outputs are stored in a structured, diffable format
- scorecard generation is deterministic for mocked or fixed-input runs

## Suggested Verification

- add tests around the score aggregation logic
