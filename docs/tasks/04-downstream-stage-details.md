# Task 04: Expand Downstream Content-Production Stage Details

## Goal

Upgrade the later pipeline stages so operators can review the actual production package instead of only summary snippets.

## Stages Covered

- `visual_translation`
- `production_brief`
- `packaging`
- `human_qc`
- `publish_queue`
- `performance_analysis`

## Why This Task Is Separate

These stages have different presentation needs from ideation stages. They are closer to execution artifacts and benefit from richer tables, grouped lists, and field-by-field inspection.

## Files To Inspect

- `dashboard/src/types/content-gen.ts`
- `dashboard/src/components/content-gen/qc-gate-panel.tsx`
- stage-panel files from Task 01
- `dashboard/src/app/content-gen/pipeline/[id]/page.tsx`

## Current Gaps To Fix

- visual translation only shows refresh check and a flattened beat coverage list
- production brief only shows location, setup, props, and assets
- packaging only shows a package header, primary hook, and alternate hooks
- publish queue hides most of the queued item details
- performance analysis hides metrics and several analysis fields
- QC is useful, but can show more of the review payload if available

## Expected Deliverables

1. `visual_translation`
   - show per-beat rows with spoken line, visual, shot type, on-screen text, assets, transition, and retention function
2. `production_brief`
   - show wardrobe, audio checks, battery checks, storage checks, pickup lines, and backup plan
3. `packaging`
   - show caption, cover text, keywords, hashtags, pinned comment, CTA, and version notes per platform
4. `human_qc`
   - preserve the approval flow
   - expose any hidden review fields that are already present in the model and useful to operators
5. `publish_queue`
   - show asset version, caption version, pinned comment, engagement plan, and cross-post targets
6. `performance_analysis`
   - show metrics in a readable way
   - expose audience signals, dropoff hypotheses, hook diagnosis, lesson, next test, backlog updates

## Implementation Notes

- Use structured layouts for dense data. A flat bullet list is not enough for visual and packaging outputs.
- Keep text overflow under control for long captions and comments.
- Treat metrics as generic key/value data because the schema is flexible.

## Acceptance Criteria

- Each covered stage shows significantly more actionable detail than before.
- The later-stage UI remains readable without requiring raw JSON inspection.
- The QC approval action continues to work.

## Test Plan

- Add or update UI tests for the most important new downstream details.
- Focus especially on packaging, publish, and performance text that proves the new fields are rendered.

## Out Of Scope

- backend payload changes
- websocket live-update behavior

