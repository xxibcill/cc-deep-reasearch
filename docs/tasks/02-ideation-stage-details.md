# Task 02: Expand Ideation Stage Details

## Goal

Upgrade the early pipeline stages to show fuller operator-facing detail using data that already exists in `PipelineContext`.

## Stages Covered

- `load_strategy`
- `plan_opportunity`
- `build_backlog`
- `score_ideas`
- `generate_angles`
- `build_research_pack`

## Why This Task Is Separate

These stages already have rich structured data in the frontend models. Most of the work is rendering, not backend invention. That makes this a good isolated task after the panel foundation is in place.

## Files To Inspect

- `dashboard/src/types/content-gen.ts`
- `dashboard/src/app/content-gen/pipeline/[id]/page.tsx`
- New files created by Task 01 under `dashboard/src/components/content-gen/stage-panels/`
- `dashboard/tests/e2e/content-gen-observability.spec.ts`

## Current Gaps To Fix

- backlog only highlights the selected item and rejection reasons
- scoring only shows chosen idea and shortlist context
- angles only show a compact selected card and brief alternates
- research pack only shows proof points, claims requiring verification, key facts, and stop reason
- opportunity and strategy views omit many existing fields

## Expected Deliverables

1. `load_strategy`
   - show audience segments
   - show proof standards
   - show forbidden claims
   - show CTA rules
   - show past winners and losers in a compact way
2. `plan_opportunity`
   - show secondary audiences
   - show research hypotheses
   - show platform and risk constraints
   - preserve the current summary fields
3. `build_backlog`
   - show more than the selected idea
   - include category, audience, why now, evidence, risk, and priority score
   - make degraded output easier to inspect
4. `score_ideas`
   - show score breakdown per shortlisted or top ideas
   - expose the per-idea scoring fields, not just total score
   - retain clear selected-idea emphasis
5. `generate_angles`
   - show selected and alternate angle details side by side or as stacked cards
   - include target audience, lens, tone, CTA, and primary takeaway
6. `build_research_pack`
   - render all list fields, including audience insights, competitor observations, examples, case studies, gaps, assets needed, unsafe claims, and verification claims

## Implementation Notes

- Reuse existing `Badge`, `Alert`, `Card`, and list styles where practical.
- Favor compact but complete operator views. Do not dump raw JSON as the primary UI.
- Use fallback text when a field exists but is empty.
- Keep the stage panels readable on both desktop and mobile.

## Acceptance Criteria

- Each covered stage surfaces materially more detail than before.
- No backend or type-model changes are required for this task.
- Selected items remain visually easy to identify.
- Empty arrays and missing values are handled gracefully.

## Test Plan

- Update or extend `dashboard/tests/e2e/content-gen-observability.spec.ts` to assert the newly visible ideation details.
- If adding more rendering branches, keep tests focused on important operator-visible strings rather than fragile DOM structure.

## Out Of Scope

- scripting step traces
- live data refresh during in-progress runs
- backend trace/model changes

