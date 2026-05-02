# P10-T1 - Split Content-Gen Pipeline Lifecycle

## Functional Feature Outcome

Pipeline stage execution is easier to change safely because lifecycle policies are isolated from stage dispatch.

## Why This Task Exists

`ContentGenPipeline` currently combines several responsibilities: deciding whether a stage can run, checking gates, summarizing input and output, building trace decisions, emitting callbacks, dispatching stage code, and handling errors. That makes a small change to one lifecycle policy require reading the whole pipeline. It also makes test coverage expensive because many assertions need a near-full pipeline setup.

## Scope

- Isolate prerequisite and gate decisions from stage dispatch.
- Isolate trace, warning, and summary construction from execution control flow.
- Preserve existing progress callback behavior.
- Preserve stage result shape and content-gen run context shape.
- Add lifecycle tests that avoid live LLM or external provider calls.

## Current Friction

- `_check_prerequisites`, `check_stage_gate`, `_summarize_input`, `_summarize_output`, warning collection, and decision summary construction live next to `run_stage`.
- Stage execution control flow is hard to test without also testing unrelated trace and summary behavior.
- The pipeline has grown into a central place for every stage policy, even when the policy could be tested independently.

## Implementation Notes

- Keep `ContentGenPipeline.run_stage()` as the compatibility entry point during this task.
- Extract behavior in small steps and add tests before moving the next lifecycle concern.
- Avoid changing stage order, stage IDs, trace field names, or dashboard-visible status values.
- Prefer dependency injection for test-only collaborators rather than monkeypatching globals.

## Test Plan

- Add unit tests for prerequisite decisions by stage.
- Add tests for stage gate pass, fail, and skipped cases.
- Add tests for trace summary output using representative stage inputs and outputs.
- Add tests for stage failure behavior and callback emission.
- Run the existing content-gen pipeline and route tests.

## Acceptance Criteria

- Stage lifecycle logic can be tested without running the full content-gen workflow.
- `run_stage` delegates lifecycle decisions instead of owning all lifecycle details inline.
- Existing trace and progress payloads remain compatible.
- No live credentials are required for the new lifecycle tests.

## Verification Commands

```bash
uv run pytest tests/test_content_gen_pipeline.py tests/test_content_gen_routes.py -x
uv run ruff check src/cc_deep_research/content_gen tests/
```

## Risks

- Trace payload changes could break audit review or dashboard inspection. Keep field names stable.
- Moving prerequisite logic can accidentally allow stages to run with incomplete context. Cover negative cases explicitly.
