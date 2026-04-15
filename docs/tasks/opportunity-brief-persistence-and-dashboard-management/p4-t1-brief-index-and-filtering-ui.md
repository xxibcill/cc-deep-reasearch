# Task P4-T1: Brief Index And Filtering UI

## Objective

Create a dashboard index for persistent briefs with the browsing ergonomics operators already expect from backlog management.

## Scope

- Add a briefs list page or panel with loading, empty, and error states.
- Support filtering by lifecycle state, approval state, source, and recency.
- Surface concise metadata such as theme, audience, revision count, approval state, and last updated time.
- Add navigation into a brief detail page.

## Acceptance Criteria

- Operators can find saved briefs without opening individual pipeline runs.
- The list view helps distinguish active drafts from approved and archived briefs quickly.
- The UI remains usable when the number of briefs grows beyond a handful.

## Advice For The Smaller Coding Agent

- Reuse list patterns from backlog where that reduces friction for operators.
- Favor clear status cues over dense metadata walls.
