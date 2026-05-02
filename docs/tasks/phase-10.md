# Phase 10 - Content-Gen Pipeline Lifecycle Split

## Functional Feature Outcome

Content-gen stage execution has smaller, testable lifecycle steps for prerequisite checks, gates, trace output, summaries, dispatch, and error handling.

## Why This Phase Exists

`content_gen/pipeline.py` is the main production entry point for content generation, but it still owns too many lifecycle responsibilities in one coordinator. Stage prerequisites, stage gates, tracing, input and output summaries, warning collection, callback handling, stage dispatch, and failure behavior are all interleaved. This phase separates those responsibilities after lane state is consolidated, reducing the cost of future stage changes and making pipeline behavior easier to test without full workflow runs.

## Scope

- Separate stage lifecycle responsibilities from the broad pipeline coordinator.
- Preserve the `ContentGenPipeline` entry point and public behavior.
- Keep stage names, run context shape, progress callbacks, and trace payloads compatible.
- Add tests around skipped stages, failed gates, trace summaries, and stage errors.

## Tasks

| Task | Summary |
| --- | --- |
| [P10-T1](../tasks/phase-10/p10-t1-split-content-gen-pipeline-lifecycle.md) | Split content-gen pipeline lifecycle behavior into focused, testable units while preserving the public pipeline entry point. |

## Dependencies

- Phase 09 should provide a stable lane state path so lifecycle changes do not also move lane rules.
- Existing content-gen route tests should remain valid because API behavior should not change.
- Current trace and audit payloads should be treated as compatibility contracts.

## Exit Criteria

- `ContentGenPipeline` remains the user-facing pipeline entry point but delegates lifecycle concerns to focused code.
- Prerequisite checks, stage gates, trace summaries, and error behavior are independently testable.
- Existing content-gen stage execution tests pass without changing user-visible behavior.
- New tests cover at least one skipped stage, one gate failure, one stage failure, and one successful traced stage.
