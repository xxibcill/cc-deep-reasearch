# Task 01: Build Pipeline Detail Stage Panel Foundation

## Goal

Refactor the content-generation pipeline detail page so each stage can own its own rendering logic. This task is structural. It should not materially expand the amount of visible data yet.

## Why This Task Comes First

`dashboard/src/app/content-gen/pipeline/[id]/page.tsx` currently contains a large `switch` statement with stage-specific rendering. The next tasks will add much more detail. That work will be hard to review and maintain unless the page is split into stage-focused components first.

## Scope

- Extract stage-specific rendering out of the page component.
- Create a clear place for shared stage-detail helpers.
- Preserve current behavior and visible content as closely as possible.

## Files To Inspect

- `dashboard/src/app/content-gen/pipeline/[id]/page.tsx`
- `dashboard/src/components/content-gen/stage-result-panel.tsx`
- `dashboard/src/components/content-gen/stage-trace-summary.tsx`
- `dashboard/src/types/content-gen.ts`

## Expected Deliverables

1. Create a new stage panel folder, for example:
   - `dashboard/src/components/content-gen/stage-panels/`
2. Move repeated helpers into small shared components or utility functions, for example:
   - section list rendering
   - summary field rendering
   - selected idea lookup helpers
   - shortlist derivation helpers
3. Replace the inline `renderStageContent()` switch with imports from stage-panel components.
4. Keep the page responsible for:
   - loading pipeline context
   - websocket status handling
   - stage ordering
   - selecting the correct stage panel

## Implementation Notes

- Do not redesign the page in this task.
- Avoid changing the current data flow.
- Prefer one stage-panel file per pipeline stage group if that keeps the write set small.
- Keep exported prop types simple and explicit.

## Acceptance Criteria

- The pipeline detail page still renders all stages and existing content.
- The large inline rendering switch is no longer the main place where stage UI lives.
- Shared helper logic is not duplicated across multiple new components.
- Existing observability tests still pass without needing rewritten expectations.

## Test Plan

- Run the relevant content-gen Playwright tests if available.
- At minimum, verify that `dashboard/tests/e2e/content-gen-observability.spec.ts` still passes unchanged.

## Out Of Scope

- Adding major new UI detail
- Backend changes
- WebSocket protocol changes

