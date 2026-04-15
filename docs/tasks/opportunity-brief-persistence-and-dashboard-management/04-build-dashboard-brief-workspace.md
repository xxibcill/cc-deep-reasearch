# Phase 04 - Build Dashboard Brief Workspace

## Functional Feature Outcome

The dashboard gains a dedicated workspace for browsing, editing, approving, and inspecting persistent opportunity briefs.

## Why This Phase Exists

The pipeline detail page is an observability surface, not a durable editorial workspace. If operators are expected to manage briefs like backlog items, the dashboard needs dedicated list and detail screens, editing and approval controls, revision visibility, and clear status cues. This phase turns the persisted backend resource into an operator-facing workflow instead of leaving it trapped inside JSON and stage panels.

## Scope

- Add a dashboard index with filters, sorting, status views, and empty states for briefs.
- Add a detail page and editor for revising, approving, and comparing brief versions.
- Integrate persistent brief identity and approval state into existing pipeline views.

## Tasks

| Task | Summary |
| --- | --- |
| [P4-T1](./p4-t1-brief-index-and-filtering-ui.md) | Build the dashboard index and browsing surface for persistent briefs. |
| [P4-T2](./p4-t2-brief-detail-editor-and-approval-ui.md) | Add a brief detail page with editing, approval, and revision controls. |
| [P4-T3](./p4-t3-pipeline-and-stage-surface-integration.md) | Connect persistent brief state back into pipeline and stage observability surfaces. |

## Dependencies

- Phase 03 must expose stable list, detail, edit, and approval APIs.
- The brief schema and lifecycle states must be finalized enough to avoid UI churn.

## Exit Criteria

- Operators can find and manage briefs without opening raw pipeline payloads.
- The dashboard clearly shows which brief version is draft, edited, approved, or superseded.
- Pipeline screens can link to the managed brief resource instead of only showing inline stage output.
