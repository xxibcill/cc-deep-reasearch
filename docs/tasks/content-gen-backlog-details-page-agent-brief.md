# Smaller Agent Brief: Backlog Details Page

## Mission

Implement a dedicated backlog item details page in the dashboard content-gen workspace.

Read this together with:

- `docs/tasks/content-gen-backlog-details-page.md`

## What To Build

Create a new route at:

- `dashboard/src/app/content-gen/backlog/[ideaId]/page.tsx`

The route should:

- load or reuse backlog data from `useContentGen`
- find the item by `idea_id`
- render a full details page for that item
- expose the same operational actions already available in the backlog overview

## Important Constraints

- Keep the implementation frontend-only unless you discover a hard blocker.
- Reuse existing store actions and API functions.
- Do not break current backlog overview actions.
- Do not revert unrelated worktree changes.

## Recommended Implementation Order

1. Extract shared backlog helpers from `backlog-panel.tsx`.
2. Build the detail page UI using those shared helpers.
3. Add navigation from grid cards and list rows into the detail page.
4. Update `ContentGenShell` so the detail route feels like backlog context.
5. Add or update Playwright coverage.

## Files You Likely Own

- `dashboard/src/app/content-gen/backlog/[ideaId]/page.tsx`
- `dashboard/src/components/content-gen/backlog-panel.tsx`
- `dashboard/src/components/content-gen/content-gen-shell.tsx`
- `dashboard/tests/e2e/backlog-management.spec.ts`

Possible helper extraction:

- `dashboard/src/components/content-gen/backlog-shared.ts`

## Existing Building Blocks To Reuse

State and actions:

- `dashboard/src/hooks/useContentGen.ts`

Client API:

- `dashboard/src/lib/content-gen-api.ts`

UI primitives:

- `dashboard/src/components/ui/badge.tsx`
- `dashboard/src/components/ui/button.tsx`
- `dashboard/src/components/ui/alert.tsx`
- `dashboard/src/components/ui/breadcrumb.tsx`
- `dashboard/src/components/ui/native-select.tsx`
- `dashboard/src/components/ui/empty-state.tsx`
- `dashboard/src/components/ui/card.tsx`

Existing editor:

- `dashboard/src/components/content-gen/backlog-item-form.tsx`

## Field Inventory

Make sure the detail page has a place for every `BacklogItem` field:

- `idea_id`
- `category`
- `idea`
- `audience`
- `problem`
- `source`
- `why_now`
- `potential_hook`
- `content_type`
- `evidence`
- `risk_level`
- `priority_score`
- `status`
- `created_at`
- `updated_at`
- `selection_reasoning`
- `latest_score`
- `latest_recommendation`
- `source_theme`
- `expertise_reason`
- `genericity_risk`
- `proof_gap_note`
- `source_pipeline_id`
- `last_scored_at`

## Action Requirements

The details page must support:

- edit item
- change status
- select item
- archive item
- delete item

Expected behavior:

- reuse the existing edit dialog
- reuse the same mutation functions from the Zustand store
- after delete, route back to `/content-gen/backlog`

## Navigation Requirements

Grid:

- clicking the card navigates to details
- action buttons must not trigger navigation

List:

- clicking the row or idea cell navigates to details
- inline controls must not trigger navigation

Detail page:

- breadcrumb or back link to backlog
- optional link to source pipeline when `source_pipeline_id` exists

## Gotchas

### 1. Shell route awareness

`ContentGenShell` currently only detects pipeline detail routes. If you do nothing, backlog detail pages may get the wrong tab/back treatment.

### 2. Store loading

The user may land directly on `/content-gen/backlog/<id>`. Do not assume backlog data is already loaded.

### 3. Not found

If backlog has finished loading and the item is missing, show a proper not-found empty state instead of rendering partial UI.

### 4. Status mismatch risk

`BacklogItemStatus` includes `runner_up`, but current UI controls do not expose it. Preserve existing operator-visible behavior unless product scope explicitly changes.

### 5. Duplicate logic

Do not copy/paste badge mappings and timestamp formatting into another large component. Extract shared helpers first.

## Suggested UI Composition

- top breadcrumb
- header with idea title and status metadata
- two-column desktop layout
- main column for content context and reasoning
- side column for actions, score, timestamps, and provenance

On mobile:

- collapse to single column
- keep action controls near the top

## Verification Checklist

- `npm test` is not enough here; add or run Playwright coverage for route navigation
- grid click opens the correct detail route
- list click opens the correct detail route
- edit works from detail page
- select or status update works from detail page
- delete returns to backlog overview
- invalid id shows not-found state

## Definition Of Done

- route exists
- route is reachable from backlog overview
- all backlog fields are visible somewhere on the detail page
- all current backlog actions are available on the detail page
- no accidental regressions in backlog overview interactions
- test coverage exists for the new route and at least one action flow
