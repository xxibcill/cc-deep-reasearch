# Task 014: Build A Repeatable Benchmark Harness

Status: Done

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

## Completion Notes

- Completed on 2026-03-07
- Added a repeatable benchmark harness and scorecard models in `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/benchmark.py`
- Added a CLI entry point with `cc-deep-research benchmark run`
- Persisted diffable benchmark outputs via `manifest.json`, `scorecard.json`, and per-case JSON files
- Documented benchmark harness usage in `/Users/jjae/Documents/guthib/cc-deep-research/README.md`
- Revalidated with `uv run pytest tests/test_benchmark.py tests/test_monitoring.py tests/test_telemetry.py tests/test_orchestrator.py` and `uv run ruff check src/cc_deep_research/benchmark.py src/cc_deep_research/monitoring.py src/cc_deep_research/cli.py src/cc_deep_research/orchestrator.py src/cc_deep_research/orchestration/planning.py src/cc_deep_research/orchestration/source_collection.py src/cc_deep_research/orchestration/analysis_workflow.py src/cc_deep_research/orchestration/execution.py tests/test_benchmark.py tests/test_monitoring.py tests/test_telemetry.py`
