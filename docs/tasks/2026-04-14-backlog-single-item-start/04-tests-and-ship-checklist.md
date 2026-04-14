# Task 04: Tests And Ship Checklist

## Objective

Verify that start-from-backlog works end to end, preserves current backlog browsing behavior, and does not introduce duplicate-run ambiguity.

## Backend Test Coverage

Add focused coverage around the new route and seeded-context behavior.

### Route tests

Add tests for:

- `POST /api/content-gen/backlog/{idea_id}/start` returns `202` and a `pipeline_id`
- missing backlog item returns `404`
- duplicate active run returns `409` and the existing `pipeline_id`
- the created job is seeded with the requested `selected_idea_id`
- the run starts from `generate_angles` (`from_stage=4`)

Likely homes:

- `tests/test_web_server.py`
- `tests/test_content_gen.py`

### Context tests

Add unit coverage for the seeded context helper if extracted.

Verify:

- backlog contains the requested item
- selected idea matches the requested item
- active candidate queue contains one primary selected candidate
- no downstream artifacts are pre-seeded
- orchestrator prerequisite checks pass for stage `generate_angles`

### Lifecycle tests

If practical, add coverage that confirms:

- the run uses `initial_context`
- stage completion updates job context normally
- scripting still marks the item `in_production`

This may already be indirectly covered by existing pipeline tests if the new route reuses the same downstream execution path.

## Frontend Verification

Prefer extending existing Playwright coverage over introducing a brand-new test surface.

Recommended file:

- `dashboard/tests/e2e/backlog-management.spec.ts`

### Overview page flow

Test:

1. open `/content-gen/backlog`
2. start a specific backlog item from the overview
3. verify navigation to `/content-gen/pipeline/{id}`
4. verify pipeline page renders the new run

### Detail page flow

Test:

1. open `/content-gen/backlog/{ideaId}`
2. click `Start Production`
3. verify navigation to pipeline detail

### Conflict flow

Test:

1. attempt start on an item already in an active run
2. verify conflict handling is intelligible
3. if frontend redirects automatically to the active run, assert that behavior

## Regression Checklist

These checks matter as much as the new action itself.

### Backlog overview

- row click still opens detail page
- edit action still works
- select action still works
- archive action still works
- delete action still works

### Backlog detail page

- page still loads directly by URL
- edit action still works
- select action still works
- archive action still works
- delete action still returns to overview

### Pipeline surfaces

- newly created run appears in pipeline list
- pipeline detail page receives normal stage updates
- no route-specific rendering hacks are required

## Manual Verification Checklist

- start from a `backlog` item on overview page
- start from the same item on detail page
- verify the same item is the selected primary lane in the pipeline context
- verify the run begins at `generate_angles`, not `build_backlog`
- verify row/card click on backlog overview still navigates instead of starting
- verify an active duplicate run does not create a second concurrent run
- verify the item becomes `in_production` only when the pipeline reaches the existing scripting transition
- verify `archived` or `published` items are handled sensibly if the UI exposes the action there

## Suggested Dev Commands

Backend:

```bash
uv run pytest tests/test_content_gen.py tests/test_web_server.py -q
```

Frontend:

```bash
cd dashboard
npm run lint
npm run test:e2e -- --grep backlog
```

If you add only a subset of tests initially, document what remains unverified rather than implying the entire surface is covered.

## Ship Bar

This slice is ready for merge when:

- a backlog item can be started from overview and detail pages
- start is explicit, not tied to row click
- the resulting run appears as a normal pipeline job
- duplicate active runs are prevented or clearly redirected
- the item-specific run starts from `generate_angles`
- backlog browsing and editing flows do not regress

## Non-Goals For This Slice

Do not expand the ship criteria to include:

- bulk launch workflows
- generalized start-from-any-stage UI
- pipeline templates per backlog item
- chat-driven launch orchestration
- major status-model redesign

## Advice For The Implementer

- Test the dangerous seams first: duplicate detection, stage index, and selected idea wiring.
- Preserve current navigation semantics on the backlog page.
- If time gets tight, cut polish before cutting conflict handling or route validation.
