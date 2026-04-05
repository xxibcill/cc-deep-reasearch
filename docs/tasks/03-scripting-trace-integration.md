# Task 03: Integrate Scripting Trace Detail Into Pipeline View

## Goal

Make the pipeline detail page show the same deep scripting-process visibility that already exists for standalone quick-script runs.

## Why This Task Is Separate

The scripting pipeline already has a detailed trace viewer in `dashboard/src/components/content-gen/quick-script-process-panel.tsx`. The pipeline detail page currently uses only `ScriptViewer`, which hides most of the useful process data already present in `PipelineContext.scripting.step_traces`.

## Files To Inspect

- `dashboard/src/components/content-gen/quick-script-process-panel.tsx`
- `dashboard/src/components/content-gen/quick-script-result-panel.tsx`
- `dashboard/src/types/content-gen.ts`
- `dashboard/src/app/content-gen/pipeline/[id]/page.tsx`
- Stage panel files created by Task 01

## Expected Deliverables

1. Update the `run_scripting` stage panel to show:
   - final script
   - execution metadata such as tone, CTA, angle, chosen structure, and word counts where useful
   - full `step_traces` via `QuickScriptProcessPanel` or a shared derivative component
2. Avoid duplicating the quick-script trace UI unless there is a strong reason.
3. If small adaptations are required, refactor the trace UI into reusable shared pieces rather than copying markup.

## Implementation Notes

- Reuse `QuickScriptProcessPanel` directly if possible.
- If the current component label text is too quick-script-specific, make that component configurable instead of creating a second version.
- Keep the final script easy to scan. The process panel should expand beneath it, not overwhelm it by default.

## Acceptance Criteria

- The pipeline detail page exposes `step_traces` for scripting runs.
- Operators can inspect:
  - per-step parsed outputs
  - per-call provider/model metadata
  - prompts and raw responses
- The standalone quick-script UI still works after any reuse-oriented refactor.

## Test Plan

- Add or extend frontend tests to verify that scripting trace metadata appears in the pipeline detail page when `step_traces` are present.
- Ensure existing tests for saved quick-script runs still pass if shared components are refactored.

## Out Of Scope

- live websocket refresh for trace data
- backend model changes
- non-scripting stage detail work

