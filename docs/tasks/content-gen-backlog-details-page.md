# Content Gen Backlog Details Page

## Goal

Add a dedicated backlog item details page for the content generation workspace so operators can move from backlog overview into a focused operational view for one idea.

The page should:

- be reachable from both backlog grid cards and backlog list rows
- show the full backlog record, not just the summary fields visible today
- expose the same item actions already supported by the backlog surface
- feel native to the existing dark, observability-style content studio

## Why This Upgrade Matters

The current backlog page works as an overview and triage surface, but it compresses too much information into a card/table view. Operators can edit, select, archive, and delete from the overview, but they cannot inspect one idea deeply without opening an edit modal or scanning dense cards.

The new details page should turn a backlog item from a compact summary into an operator workspace.

## Route And Navigation

### New route

- `dashboard/src/app/content-gen/backlog/[ideaId]/page.tsx`
- canonical URL: `/content-gen/backlog/<idea_id>`

### Entry points

- Grid view: clicking the card body navigates to the details page.
- List view: clicking the idea cell or row navigates to the details page.
- Inline controls inside the card/row must continue to work without triggering navigation.

### Supporting navigation

- Add breadcrumb or back-link flow:
  - `Content Studio / Backlog / <short idea label>`
- The details page should keep the user inside the content-gen shell.
- The shell should treat backlog detail as a backlog-context page, not as generic overview.

## Product Decisions

### In scope

- new backlog details route
- navigation from grid and list views
- full backlog information display
- item actions on the details page
- empty/not-found state for invalid `idea_id`
- tests for navigation and key actions

### Out of scope

- backend schema changes
- new backlog actions that do not already exist in store/API
- redesign of the entire backlog overview page
- cross-entity workflow changes outside backlog navigation

## Page Structure

Use the current dashboard language: dark mode, information-dense, precise, operator-facing. Avoid decorative hero treatment. This page should feel like a focused inspection surface.

### 1. Header summary

Top section should show the highest-signal state:

- idea title
- idea id
- status badge
- category badge
- recommendation badge
- latest score
- priority score
- risk level
- updated timestamp

Recommended treatment:

- title and metadata on the left
- score/status stack on the right
- breadcrumb above
- subtle back action to return to backlog

### 2. Sticky action rail

Keep user actions easy to reach without forcing scroll back to the top.

Actions to support:

- edit item
- change status
- select item
- archive item
- delete item

Recommended behavior:

- primary workflow action: `Select item` when not selected
- status select stays visible
- destructive action remains separated from non-destructive controls
- after delete, navigate back to `/content-gen/backlog`

### 3. Details content sections

Organize fields into readable sections instead of one long properties list.

#### Editorial summary

- `idea`
- `audience`
- `problem`
- `why_now`
- `potential_hook`
- `content_type`

#### Scoring and decisioning

- `latest_score`
- `priority_score`
- `latest_recommendation`
- `selection_reasoning`
- `expertise_reason`
- `genericity_risk`
- `proof_gap_note`
- `last_scored_at`

#### Evidence and provenance

- `source_theme`
- `source`
- `evidence`
- `source_pipeline_id`
- link to `/content-gen/pipeline/<source_pipeline_id>` when present

#### Operational metadata

- `status`
- `category`
- `risk_level`
- `created_at`
- `updated_at`

### 4. Empty field handling

This page should still be useful when many fields are missing.

- For absent fields, render a muted placeholder such as `Not captured yet`.
- Do not collapse the entire section just because one field is empty.
- If `source_pipeline_id` is missing, omit the link only, not the section.

## UX Notes

### Grid/list click behavior

- Grid cards should feel clickable, but buttons and form triggers inside the card must stop navigation.
- List rows can be row-clickable or idea-cell-clickable. If row-clickable, action buttons and selects must stop propagation.

### Keyboard and accessibility

- Card or row entry points must remain keyboard reachable.
- Do not hide navigation behind pointer-only behavior.
- Buttons need explicit labels or titles.
- Breadcrumb should expose the current page correctly.

### Not-found state

If the backlog list has loaded and the item is missing:

- show a clear empty state
- include a link/button back to `/content-gen/backlog`
- do not throw or leave the page blank

## Implementation Notes

### Reuse existing store and API

Do not add a new item-detail endpoint unless truly necessary. The store already supports:

- `loadBacklog`
- `updateBacklogItem`
- `selectBacklogItem`
- `archiveBacklogItem`
- `deleteBacklogItem`

The detail page can load backlog items and derive the target item from the store by `idea_id`.

### Extract shared backlog presentation helpers

The following logic already exists in `backlog-panel.tsx` and should be shared instead of duplicated:

- `formatTimestamp`
- status badge variant mapping
- recommendation badge variant mapping
- status option list

Suggested extraction:

- `dashboard/src/components/content-gen/backlog-shared.ts`

This will keep the backlog overview and detail page visually aligned.

### Shell behavior

`ContentGenShell` currently special-cases pipeline detail routes only. Extend it so backlog detail routes:

- keep backlog context visible
- show a sensible back affordance
- do not mis-highlight the tab state

### Status options caveat

`BacklogItemStatus` includes `runner_up`, but the current backlog UI only exposes:

- `backlog`
- `selected`
- `in_production`
- `published`
- `archived`

Preserve current behavior unless you intentionally decide to expose `runner_up` everywhere. Do not introduce status drift by accident.

## Acceptance Criteria

- A backlog item detail page exists at `/content-gen/backlog/[ideaId]`.
- Users can open the page from both backlog grid and backlog list views.
- The page displays all `BacklogItem` fields in a structured, readable way.
- Users can edit, update status, select, archive, and delete the item from the details page.
- Delete returns the user to the backlog overview after success.
- The page handles missing fields gracefully.
- The page shows a clear not-found state for unknown items.
- Navigation and actions work in both mouse and keyboard flows.
- Existing backlog overview actions still work after adding navigation.

## Test Coverage

Add or extend Playwright coverage for:

- grid card navigation to detail page
- list row or idea-cell navigation to detail page
- detail page renders the correct idea title and metadata
- detail page action flow for select or status update
- delete from detail page returns to backlog overview
- unknown backlog id shows not-found UI

## Suggested File Touches

- `dashboard/src/app/content-gen/backlog/[ideaId]/page.tsx`
- `dashboard/src/components/content-gen/backlog-panel.tsx`
- `dashboard/src/components/content-gen/content-gen-shell.tsx`
- `dashboard/src/components/content-gen/backlog-item-form.tsx` if trigger flexibility is needed
- `dashboard/src/components/content-gen/backlog-shared.ts` or similar extracted helper file
- `dashboard/tests/e2e/backlog-management.spec.ts` or a new dedicated backlog detail spec

## Design Direction

Stay close to the product’s existing character:

- analytical
- transparent
- reliable

This should feel like an operator console for one backlog record, not a marketing detail page. Favor dense clarity, restrained motion, and obvious operational controls.
