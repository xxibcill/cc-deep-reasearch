# Task 015: Add Workflow Observability And Stop Reasons

Status: Done

## Objective

Improve telemetry so retrieval quality and iteration behavior can be debugged without reading orchestrator internals.

## Scope

- add telemetry for:
  - query variation generation
  - source provenance by variation
  - analysis mode selection
  - follow-up query reasons
  - iteration stop reasons
- standardize stop-reason values for success, limit reached, low quality, and degraded execution

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/monitoring.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/telemetry.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestrator.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_monitoring.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_telemetry.py`

## Dependencies

- [006_query_family_expansion.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/006_query_family_expansion.md)
- [007_source_provenance_tracking.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/007_source_provenance_tracking.md)

## Acceptance Criteria

- iteration stop reasons are emitted consistently
- telemetry can distinguish which query family drove useful results
- tests cover the new event payloads

## Suggested Verification

- run `pytest tests/test_monitoring.py tests/test_telemetry.py`

## Completion Notes

- Completed on 2026-03-07
- Added standardized stop reasons and richer observability events in `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/monitoring.py`
- Emitted telemetry for query variation generation, analysis mode selection, source provenance, follow-up decisions, and iteration stop reasons across planning and workflow services
- Propagated session stop-reason finalization through `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestration/execution.py` and `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/cli.py`
- Added tests covering the new telemetry payloads in `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_monitoring.py` and `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_telemetry.py`
- Revalidated with `uv run pytest tests/test_benchmark.py tests/test_monitoring.py tests/test_telemetry.py tests/test_orchestrator.py` and `uv run ruff check src/cc_deep_research/benchmark.py src/cc_deep_research/monitoring.py src/cc_deep_research/cli.py src/cc_deep_research/orchestrator.py src/cc_deep_research/orchestration/planning.py src/cc_deep_research/orchestration/source_collection.py src/cc_deep_research/orchestration/analysis_workflow.py src/cc_deep_research/orchestration/execution.py tests/test_benchmark.py tests/test_monitoring.py tests/test_telemetry.py`
