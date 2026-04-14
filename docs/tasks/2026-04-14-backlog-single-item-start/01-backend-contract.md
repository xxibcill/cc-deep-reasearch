# Task 01: Backend Contract

## Objective

Add a backend entrypoint that starts a pipeline from one persisted backlog item without re-running backlog ideation or scoring.

## Route Contract

Create a dedicated endpoint:

- `POST /api/content-gen/backlog/{idea_id}/start`

Recommended success status:

- `202 Accepted`

This should behave like the existing async pipeline start endpoint: create a job immediately, schedule work in the background, and return enough metadata for the frontend to navigate to the pipeline detail screen.

## Why A Dedicated Route

The current generic pipeline route accepts:

- `theme`
- `from_stage`
- `to_stage`

That route models "start a pipeline from theme-level inputs."

This feature models something materially different:

- use a persisted backlog item
- preselect exactly one candidate
- bypass ideation stages
- begin downstream production work

Combining both behaviors behind one generic request would add ambiguity to validation, telemetry, and frontend usage. The dedicated route makes the behavior explicit and easier to test.

## Recommended Response Shape

Suggested response:

```json
{
  "pipeline_id": "abc123def456",
  "status": "queued",
  "idea_id": "backlog-item-1",
  "from_stage": 4,
  "to_stage": 13
}
```

The exact response may mirror the existing job summary helper if that is easier, but the response should at minimum include:

- `pipeline_id`
- enough status information for the UI to know the run exists

## Error Cases

### `404 Not Found`

Return when:

- the backlog item does not exist

Suggested body:

```json
{ "error": "Backlog item not found" }
```

### `409 Conflict`

Return when:

- a non-terminal pipeline run already exists for the same backlog item

Suggested body:

```json
{
  "error": "Backlog item is already in an active pipeline",
  "pipeline_id": "existing-active-pipeline-id"
}
```

The frontend can then redirect to or offer `Open active run`.

### `400 Bad Request`

Use only for real input/state validation failures, such as:

- the item exists but the seeded context cannot satisfy the required starting stage

This should be rare if the seeding logic is implemented correctly.

### `500 Internal Server Error`

Use existing route patterns:

- log the exception
- mark the job failed if job creation already happened
- publish the failure event if the run entered the job lifecycle

## Execution Model

Follow the same high-level async pattern used by the existing pipeline routes:

1. load config
2. load backlog item
3. create a pipeline job
4. seed a `PipelineContext`
5. attach the seeded context to the job registry
6. launch an async task that calls `run_full_pipeline(...)`
7. update the job registry and event stream as stages progress

This is intentionally similar to the existing "resume pipeline with initial context" path so that:

- pipeline detail pages work without special cases
- WebSocket events continue to flow through the same channel
- operator observability stays consistent

## New Request Model

The route does not need a request body for v1.

Path parameter only:

- `idea_id`

Optional future expansion can add a request model for:

- alternate end stage
- force restart despite duplicate active run
- dry run or validation only

Do not add these in v1 unless the frontend already needs them.

## Seeding Responsibilities

This route owns the responsibility for building the minimal valid `PipelineContext` needed to start from `generate_angles`.

Recommended helper shape:

- `_build_pipeline_context_from_backlog_item(...) -> PipelineContext`

Keep the helper near the router or in a dedicated content-gen helper module. Avoid burying this inside unrelated backlog service code because this logic belongs to pipeline startup, not backlog persistence.

## Minimal Seeded Context

The seeded `PipelineContext` should include:

- `pipeline_id`
- `theme`
- `created_at`
- `current_stage`
- `strategy`
- `backlog`
- `selected_idea_id`
- `shortlist`
- `selection_reasoning`
- `runner_up_idea_ids=[]`
- `active_candidates=[primary selected candidate]`
- empty lane outputs for downstream stages

Recommended values:

- `theme = item.source_theme or item.idea`
- `backlog = BacklogOutput(items=[item])`
- `selected_idea_id = item.idea_id`
- `shortlist = [item.idea_id]`
- `selection_reasoning = item.selection_reasoning or "Started explicitly by operator from backlog."`
- `active_candidates = [PipelineCandidate(idea_id=item.idea_id, role="primary", status="selected")]`

Do not try to fake scoring data unless the orchestrator truly requires it. The current candidate resolution logic can already derive a valid primary lane from `selected_idea_id` and `active_candidates`.

## Starting Stage

Use:

- `from_stage = 4`

That maps to `generate_angles`.

Why not earlier:

- `build_backlog` would regenerate backlog ideas from a theme and bypass the user’s explicit item choice
- `score_ideas` would re-score and possibly re-select instead of respecting the operator’s selection

Why not later:

- `build_research_pack` requires an angle
- `build_argument_map` requires research pack plus angle
- `run_scripting` requires argument map plus angle

`generate_angles` is the earliest stage that preserves the chosen item while satisfying downstream prerequisites incrementally.

## Duplicate Active Run Guard

This route should reject starting the same backlog item if there is already an active job for it.

Recommended matching strategy:

Inspect current jobs in the registry and treat a job as matching when:

- it is not terminal
- its pipeline context resolves the same `selected_idea_id`

Fallback match:

- compare route `idea_id` against the job context’s `selected_idea_id`
- if the job context is not yet attached, compare against an explicit metadata field if you decide to add one to the job record

Do not rely on theme matching. Different items may share the same theme.

## Telemetry And Job Summary

Keep this consistent with the existing pipeline system:

- the job should appear in `/api/content-gen/pipelines`
- stage events should be published with the same event types
- pipeline detail pages should render without route-specific branching

If useful, extend job summary metadata with:

- `selected_idea_id`

That is optional for v1 but improves operator visibility and helps duplicate-run checks if surfaced at the job layer.

## Suggested Router Flow

Pseudo-flow:

1. `service = BacklogService(config)`
2. `backlog = service.load()`
3. `item = next(... by idea_id ...)`
4. if missing: `404`
5. if duplicate active run: `409`
6. `job = job_registry.create_job(theme=<seeded theme>, from_stage=4, to_stage=end)`
7. `ctx = build_seeded_context(job.pipeline_id, item, strategy)`
8. `job_registry.update_context(job.pipeline_id, ctx)`
9. async run:
   - `orch.run_full_pipeline(ctx.theme, from_stage=4, to_stage=end, initial_context=ctx, ...)`
10. return queued job summary

## Service Boundary Guidance

Keep responsibilities separate:

- `BacklogService` remains the source of truth for loading and updating backlog items
- the router or pipeline-start helper owns seeded context creation
- the orchestrator remains unchanged as much as possible

Avoid adding "start pipeline" behavior to `BacklogService`. That would mix persistence and orchestration concerns.

## Acceptance Criteria

- A request to `POST /api/content-gen/backlog/{idea_id}/start` creates a new async pipeline job.
- The new run starts from `generate_angles`.
- The run is seeded with exactly one primary candidate matching the requested backlog item.
- Existing pipeline detail pages and event streams work for the new run.
- Missing item returns `404`.
- Duplicate active run returns `409` with the active `pipeline_id`.

## Advice For The Implementer

- Use the existing resume-with-initial-context path as the behavioral template.
- Keep the seeded context minimal. Extra fake data will create long-term maintenance cost.
- Make duplicate-run checks explicit before scheduling work.
- Do not special-case downstream stage behavior unless a real prerequisite gap appears in tests.
