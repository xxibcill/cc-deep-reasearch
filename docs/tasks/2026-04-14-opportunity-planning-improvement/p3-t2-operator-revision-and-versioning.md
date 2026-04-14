# Task P3-T2: Operator Revision And Versioning

## Objective

Allow operators to revise, approve, and version opportunity briefs before the pipeline commits more work downstream.

## Scope

- Add an editable opportunity-brief workflow in the dashboard.
- Support approval and revision states.
- Preserve revision history or version metadata.

## Acceptance Criteria

- Operators can revise a generated brief instead of treating it as read-only.
- The system can distinguish generated, edited, and approved brief versions.
- Downstream stages can use the approved version deliberately.

## Advice For The Smaller Coding Agent

- Keep the first editing flow narrow and auditable.
- Preserve generated content and operator edits separately where possible.
