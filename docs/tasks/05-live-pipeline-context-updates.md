# Task 05: Add Live Pipeline Context Updates During Execution

## Goal

Make the pipeline detail page update stage content live while a pipeline is running, not only after the full run completes.

## Problem Statement

The current pipeline detail page updates `stageStates` from websocket events, but the actual `pipelineContext` is fetched only through `selectPipeline()` and is not refreshed on each stage completion. On the backend, the job registry is updated with full context only after the entire run completes. That means the operator sees stage badges move, but detailed stage content lags behind until the run is over.

## Files To Inspect

- `dashboard/src/app/content-gen/pipeline/[id]/page.tsx`
- `dashboard/src/hooks/useContentGen.ts`
- `dashboard/src/lib/content-gen-api.ts`
- `src/cc_deep_research/content_gen/router.py`
- `src/cc_deep_research/content_gen/progress.py`
- `src/cc_deep_research/content_gen/orchestrator.py`

## Expected Deliverables

1. Backend
   - update the in-memory job context after each stage completes or is skipped
   - publish websocket payloads that let the frontend receive the latest context while the run is still active
2. Frontend
   - consume live context updates and merge them into store state
   - refresh the active pipeline detail view without requiring a full manual refetch
3. Preserve current terminal states:
   - completed
   - failed
   - cancelled

## Recommended Approach

- Add a dedicated websocket message for context updates, or attach fresh `context` to existing stage-completed messages.
- Keep payloads explicit and stable. Avoid fragile implicit behavior.
- Update Zustand state in `useContentGen` instead of handling all state locally inside the page component if that makes the flow cleaner.

## Acceptance Criteria

- During an active run, stage content appears progressively as stages complete.
- Reloading the detail page mid-run still shows the latest known context.
- Existing websocket status behavior continues to work.
- No polling loop is required for normal live updates.

## Test Plan

- Add a focused frontend test that simulates websocket messages with updated context and verifies the page updates without a full-page reload.
- Add backend tests if there is already a suitable router or websocket test pattern in the repo.

## Out Of Scope

- redesigning stage trace schemas
- adding new trace fields beyond what is necessary to send current context live

