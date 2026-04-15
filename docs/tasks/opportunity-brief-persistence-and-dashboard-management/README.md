# Opportunity Brief Persistence And Dashboard Management Task Pack

## Goal

Make `OpportunityBrief` a first-class persistent resource that operators can list, inspect, revise, approve, version, and deliberately use from the dashboard in the same way the backlog is managed today.

## Current State

The repo already treats `OpportunityBrief` as an important pipeline artifact, but not yet as a durable operator-managed workspace.

- `OpportunityBrief` exists in `src/cc_deep_research/content_gen/models.py` and already carries early versioning fields such as `version`, `is_generated`, `is_approved`, and `revision_history`.
- The opportunity-planning stage produces the brief inside pipeline execution, but the brief mostly lives inside `PipelineContext` or saved pipeline jobs.
- The dashboard can inspect the opportunity brief on a pipeline detail page, but there is no dedicated list/detail/edit/approval workspace comparable to backlog management.
- Backlog has a clear persistence, service, API, and dashboard pattern that brief management can reuse conceptually.
- The earlier task [`docs/tasks/2026-04-14-opportunity-planning-improvement/p3-t2-operator-revision-and-versioning.md`](../2026-04-14-opportunity-planning-improvement/p3-t2-operator-revision-and-versioning.md) identified the need, but the work is too large for one task.

Relevant implementation:

- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/agents/opportunity.py`
- `src/cc_deep_research/content_gen/progress.py`
- `src/cc_deep_research/content_gen/router.py`
- `src/cc_deep_research/content_gen/backlog_service.py`
- `src/cc_deep_research/content_gen/storage/`
- `dashboard/src/components/content-gen/stage-panels/plan-opportunity-panel.tsx`
- `dashboard/src/lib/content-gen-api.ts`
- `dashboard/src/types/content-gen.ts`
- `docs/content-gen-artifact.md`

## Product Intent

Opportunity planning should become a durable editorial control surface, not just a stage output embedded in a pipeline run.

Operators should be able to:

- keep generated briefs after a run ends
- refine briefs without overwriting the original generation
- approve a specific version before downstream work proceeds
- compare versions and track who changed what
- start backlog generation or deeper execution from an approved brief deliberately
- use AI assistance for proposal generation while keeping persistence behind explicit apply actions

## Recommended Rollout

Use a 6-phase plan:

1. Establish a persistent brief domain model and storage boundary.
2. Integrate persisted and approved briefs into pipeline execution and resume flows.
3. Expose a safe backend management surface with auditability and conflict control.
4. Build a dedicated dashboard workspace for brief browsing, editing, and approval.
5. Add AI-assisted brief refinement and explicit backlog handoff workflows.
6. Finish migration, hardening, observability, testing, and rollout guardrails.

## Non-Goals

Do not redesign the entire content-generation pipeline around a new CMS abstraction in the first implementation.

Do not collapse backlog and brief into one generic artifact type unless that simplification is proven by the implementation.

Do not allow AI endpoints to mutate persisted brief state without an explicit operator apply step.

Do not block basic opportunity generation on advanced analytics, template libraries, or organization-wide governance features.

## Task Files

- `01-establish-persistent-brief-domain.md`
- `02-integrate-briefs-into-pipeline-execution.md`
- `03-expose-brief-management-backend.md`
- `04-build-dashboard-brief-workspace.md`
- `05-add-ai-assisted-brief-operations.md`
- `06-harden-migrate-and-roll-out.md`
- `p1-t1-brief-resource-model-and-lifecycle.md`
- `p1-t2-brief-store-and-service.md`
- `p1-t3-brief-version-history-and-migration-contract.md`
- `p2-t1-pipeline-context-reference-model.md`
- `p2-t2-approved-brief-execution-gates.md`
- `p2-t3-resume-clone-and-seeded-run-flows.md`
- `p3-t1-brief-management-api.md`
- `p3-t2-audit-history-and-conflict-control.md`
- `p3-t3-permissions-and-apply-contracts.md`
- `p4-t1-brief-index-and-filtering-ui.md`
- `p4-t2-brief-detail-editor-and-approval-ui.md`
- `p4-t3-pipeline-and-stage-surface-integration.md`
- `p5-t1-brief-assistant-workspace.md`
- `p5-t2-brief-to-backlog-apply-flow.md`
- `p5-t3-brief-reuse-compare-and-branching.md`
- `p6-t1-backward-compatibility-and-data-migration.md`
- `p6-t2-observability-tests-and-failure-recovery.md`
- `p6-t3-operator-docs-rollout-and-guardrails.md`

## Advice For The Implementer

- Treat the brief as a managed resource with its own lifecycle, not just another blob inside `PipelineContext`.
- Preserve the generated original and operator edits separately where possible.
- Reuse the backlog architecture where it helps, but do not force one-to-one reuse if the brief lifecycle is materially different.
- Put approval and explicit downstream handoff at the center of the design. That is what turns persistence into a meaningful operator workflow.
