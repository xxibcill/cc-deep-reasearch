# Task 02: Frontend Workflow

## Objective

Expose a safe, explicit `Start Production` action from both backlog surfaces:

- backlog overview page
- backlog detail page

The action should start exactly one backlog item and then take the operator to the resulting pipeline run.

## UX Principles

### 1. Do not overload row click

The current backlog overview uses row/card click to navigate to detail. Preserve that behavior.

Starting production is:

- expensive
- stateful
- irreversible in practice from an operator workflow perspective

It should always require a deliberate control.

### 2. Use the same action label everywhere

Recommended label:

- `Start Production`

This is clearer than:

- `Start`
- `Run`
- `Process`

because it describes the business intent, not just the transport.

### 3. Make success transition obvious

After success, the user should land on:

- `/content-gen/pipeline/{pipeline_id}`

Do not leave the user on the backlog page with a silent toast-only confirmation. The pipeline detail view is where progress is visible.

## Pages And Components To Update

Primary targets:

- `dashboard/src/components/content-gen/backlog-panel.tsx`
- `dashboard/src/app/content-gen/backlog/[ideaId]/page.tsx`
- `dashboard/src/lib/content-gen-api.ts`
- `dashboard/src/hooks/useContentGen.ts`
- `dashboard/src/types/content-gen.ts`

Optional minor touchpoints:

- pipeline summaries if you decide to surface selected idea metadata

## Recommended UI Changes

### Backlog overview

Add a new explicit action in `renderItemActions(...)`.

Placement options:

- a button next to existing icon actions
- a small overflow menu if the action cluster is already too dense

Recommended v1:

- add a compact button with a text label in grid cards
- add either a compact text button or a small icon-plus-tooltip in list rows

The key constraint is clarity. The operator should not have to guess whether the action selects, edits, or starts work.

### Backlog detail page

Add `Start Production` in the sticky action rail.

Recommended hierarchy:

- `Start Production` should be visually stronger than `Select item`
- `Edit`, `Select`, and status dropdown can remain secondary controls

This is the page where the operator has full context, so it should present the primary action most clearly.

## Loading And Disabled States

The UI should prevent duplicate clicks while the start request is in flight.

Recommended behavior:

- disable only the clicked item’s start control on backlog overview
- disable the detail-page start button while the request is pending
- keep unrelated item actions usable if practical

Suggested labels during request:

- `Starting...`

If the route returns `409` with an existing `pipeline_id`, the UI should not show a generic error. It should offer a direct way to open the active run.

## Conflict Handling

When the backend returns `409` because the item is already in an active run:

Recommended UX:

1. show inline error or warning near the action
2. include a link or automatic redirect to the active pipeline

Preferred v1 behavior:

- redirect directly to the existing pipeline if `pipeline_id` is present in the response

That resolves operator intent faster and keeps the surface simple.

## Store And API Shape

### API helper

Add a dedicated helper in `dashboard/src/lib/content-gen-api.ts`:

- `startBacklogItem(ideaId: string): Promise<{ pipeline_id: string; ... }>`

Do not force the backlog pages to reuse the generic `startPipeline(...)` helper. The backend route is purpose-specific, and the client helper should reflect that.

### Store method

Recommended addition in `useContentGen.ts`:

- `startBacklogItem: (ideaId: string) => Promise<string | null>`

Suggested method responsibilities:

- clear prior error
- call the API helper
- optionally refresh pipeline list after success
- return `pipeline_id` so caller can route
- keep error state consistent with other store actions

If you prefer to keep this page-local instead of store-managed, that is acceptable. The main requirement is to avoid duplicated request logic across overview and detail pages.

## Type Additions

Add minimal frontend types for the new start route response.

Suggested type:

```ts
export interface StartBacklogItemResponse {
  pipeline_id: string;
  status?: string;
  idea_id?: string;
  from_stage?: number;
  to_stage?: number;
}
```

If the backend returns the full pipeline summary shape, reusing an existing summary type is also fine.

## Navigation Behavior

After a successful start:

- `router.push(`/content-gen/pipeline/${pipelineId}`)`

Do not open in a new tab.
Do not leave the user on the backlog page waiting for them to manually discover the run.

## Visual And Interaction Notes

- Preserve the existing dashboard tone and density.
- Avoid turning the backlog page into a launchpad with oversized CTA buttons everywhere.
- Use a control that is easy to scan but still secondary to the editorial content of the item.
- On detail page, the CTA can be more prominent because intent is stronger there.

## Empty / Terminal Status Considerations

Recommended v1 rules:

- allow start from `backlog`
- allow start from `selected`
- allow start from `runner_up` if surfaced
- block or discourage start from `archived`
- block start from `published`
- if already `in_production`, rely on backend duplicate guard or return a clearer message

The frontend can implement light affordances such as disabling the button for obviously terminal statuses, but the backend must remain the real authority.

## Acceptance Criteria

- A user can start a backlog item from the overview page.
- A user can start a backlog item from the detail page.
- Starting is explicit and separate from row click navigation.
- A successful start takes the user to the pipeline detail page.
- Duplicate active runs are handled gracefully.
- Existing backlog edit/select/archive flows still work.

## Advice For The Implementer

- Reuse one API path and one handler path across both surfaces.
- Prefer slightly more explicit UI over compact-but-ambiguous iconography.
- Keep optimistic updates minimal. The source of truth for active progress is the pipeline detail page, not the backlog list.
