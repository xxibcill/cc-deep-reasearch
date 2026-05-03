# Phase 17 - Legacy Content-Gen Orchestrator Slimdown

## Functional Feature Outcome

The deprecated `ContentGenOrchestrator` remains compatible for downstream callers while `legacy_orchestrator.py` is reduced to a thin adapter around the canonical pipeline, brief, and scripting services.

## Why This Phase Exists

`src/cc_deep_research/content_gen/legacy_orchestrator.py` is the largest source file in the codebase at roughly 35k tokens and 4.1k lines. It is documented as a compatibility path, but it still contains duplicate pipeline execution, stage handlers, trace logic, brief lifecycle helpers, and scripting iteration helpers. This makes content-gen changes harder for AI agents and humans because normal execution lives in `ContentGenPipeline` while a second legacy implementation still has to be understood.

## Scope

- Preserve the deprecated `ContentGenOrchestrator` import path and public compatibility methods.
- Extract pure targeted-revision helpers and brief-run reference logic into focused modules.
- Delegate full-pipeline and standalone scripting execution to `ContentGenPipeline` and `ScriptingRunService`.
- Remove dead legacy stage handlers after compatibility delegation is covered by tests.
- Keep behavior unchanged for existing content-gen API routes, resume flows, brief flows, and targeted-revision tests.

## Tasks

| Task | Summary |
| --- | --- |
| [P17-T1](phase-17/p17-t1-compatibility-surface-audit.md) | Audit and freeze the `ContentGenOrchestrator` compatibility surface before moving code |
| [P17-T2](phase-17/p17-t2-targeted-revision-helpers.md) | Extract targeted revision helpers from `legacy_orchestrator.py` into a focused module |
| [P17-T3](phase-17/p17-t3-brief-run-reference-service.md) | Extract brief run reference and managed-brief compatibility logic |
| [P17-T4](phase-17/p17-t4-delegate-legacy-execution.md) | Delegate deprecated orchestrator execution to `ContentGenPipeline` and `ScriptingRunService` |
| [P17-T5](phase-17/p17-t5-remove-legacy-stage-handlers.md) | Remove duplicate legacy stage handlers and enforce the slim compatibility adapter |

## Dependencies

- `ContentGenPipeline` owns normal pipeline stage sequencing and trace creation.
- `ScriptingRunService` owns standalone scripting and iterative scripting execution.
- `StagePrerequisitePolicy`, `StageGatePolicy`, and `StageTracePolicy` cover lifecycle behavior outside legacy dispatch.
- Existing tests for content-gen pipeline boundaries, gates, brief flows, iterative loop helpers, and web routes must remain available.

## Exit Criteria

- `legacy_orchestrator.py` no longer defines `_PIPELINE_HANDLERS` or `_stage_*` pipeline handler functions.
- `ContentGenOrchestrator.run_full_pipeline()` delegates to `ContentGenPipeline`.
- `ContentGenOrchestrator.run_scripting*()` delegates to `ScriptingRunService`.
- Static targeted-revision compatibility methods are wrappers around the extracted helper module.
- Brief reference compatibility methods are wrappers around an extracted service.
- `legacy_orchestrator.py` is reduced below 5k measured `o200k_base` tokens.
- Focused checks pass: `uv run ruff check src/ tests/`, `uv run mypy src/`, and the content-gen pipeline, brief, iterative-loop, and route regression tests.
