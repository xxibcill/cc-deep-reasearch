# P9-T1 - Consolidate Content-Gen Lane State

## Functional Feature Outcome

Content-gen lane behavior is consistent across pipeline execution, stage execution, and legacy compatibility calls.

## Why This Task Exists

Lane behavior is currently implemented in several places, including `content_gen/pipeline.py`, stage orchestrators such as research and scripting, and `content_gen/legacy_orchestrator.py`. The repeated helpers resolve lane items, find lane angles, ensure lane context, record completion, and sync primary lane output. That duplication makes multi-lane changes risky because there is no single place to validate the domain rules.

## Scope

- Inventory the duplicated lane helpers in pipeline, stage, and legacy content-gen modules.
- Extract the shared lane behavior into a single in-process domain path.
- Replace duplicated helper calls without changing persisted context shape.
- Keep legacy orchestrator compatibility behavior intact while removing redundant logic where practical.
- Add regression tests for lane state edge cases.

## Current Friction

- `_resolve_lane_angle`, `_ensure_lane_context`, `_record_lane_completion`, and `_sync_primary_lane` exist in multiple content-gen modules.
- Stage code repeats lane candidate handling before it delegates to agent or stage-specific work.
- The primary lane can be updated from several places, making it hard to reason about which stage owns final output.
- The legacy orchestrator still carries copies of lane helpers even though the pipeline is the preferred entry point.

## Implementation Notes

- Keep the first change narrow and behavior-preserving.
- Prefer a plain in-process helper or service that works with existing context dictionaries and typed models.
- Do not change API payloads, saved run context, or dashboard type contracts in this task.
- Leave legacy deletion for a later phase; this task should only make legacy code call the canonical lane behavior where safe.
- Document any remaining intentional differences between stage-specific lane handling and shared lane behavior.

## Test Plan

- Add focused tests for lane item lookup, missing lane fallback, and primary-lane fallback.
- Add tests that completion recording updates both lane context and primary context as expected.
- Add tests for multi-lane execution where one lane has explicit angle data and another relies on fallback context.
- Run existing content-gen pipeline and scripting tests that cover lane behavior.

## Acceptance Criteria

- The duplicated lane helper logic is removed or reduced to thin compatibility calls.
- Equivalent inputs produce equivalent lane context updates across pipeline and stage execution.
- Primary lane synchronization is covered by tests.
- Legacy compatibility tests still pass.

## Verification Commands

```bash
uv run pytest tests/test_content_gen_pipeline.py tests/test_content_gen_briefs.py tests/test_iterative_loop.py -x
uv run mypy src/cc_deep_research/content_gen/pipeline.py src/cc_deep_research/content_gen/stages/
```

## Risks

- Lane state is persisted inside content-gen context payloads. Keep serialized keys stable.
- Some duplicated code may hide subtle stage-specific differences. Preserve and test any intentional differences instead of flattening them blindly.
