# Task P2-T3: Superuser Bulk Actions

## Objective

Let superusers act on AI recommendations across many backlog items without editing each record manually.

## Scope

- Support bulk proposal sets such as:
  - promote top N
  - archive weak duplicates
  - enrich selected sparse items
  - reclassify items by category or theme
- Add approval controls for apply-selected and reject-selected.
- Record the result of each operation so failures do not disappear in a batch workflow.

## Acceptance Criteria

- A superuser can approve and apply recommendations across multiple backlog items in one workflow.
- Batch execution surfaces per-item outcomes clearly.
- Bulk actions reduce repeated manual CRUD without weakening validation rules.

## Status

**Done** — Implemented in:
- `dashboard/src/components/content-gen/triage-workspace.tsx` — bulk checkbox selection, selectAll/deselectAll per group, applySelected/rejectSelected with per-item outcomes

## Advice For The Smaller Coding Agent

- Keep the first bulk-action set narrow and tied to validated item operations.
- Do not introduce hidden mass-edit behavior.
- Bias toward recoverable workflows with explicit operator control.
