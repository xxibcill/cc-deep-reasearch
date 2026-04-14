# Phase 01 - Superuser AI Triage Workspace

## Functional Feature Outcome

Superusers can review, enrich, deduplicate, and batch-update backlog items through an AI-assisted workspace without allowing autonomous writes.

## Why This Phase Exists

The current backlog already supports persistence, scoring metadata, manual CRUD, and advisory backlog chat, but the highest-friction work is still manual triage. This phase adds the first meaningful AI performance lift by moving the system from single-item editing toward batch editorial operations with explicit review and apply controls.

## Scope

- Add an AI triage workspace directly to backlog management for superusers.
- Support AI-generated batch proposals for enrichment, reframing, dedupe, and prioritization.
- Keep `BacklogService` as the only persistence path and require explicit operator apply.

## Tasks

| Task | Summary |
| --- | --- |
| [P1-T1](../tasks/phase-01/p1-t1-superuser-triage-contract.md) | Add backend contracts and validation for batch AI triage proposals. |
| [P1-T2](../tasks/phase-01/p1-t2-superuser-triage-workspace.md) | Build the backlog-page triage workspace for reviewing and applying AI proposals. |
| [P1-T3](../tasks/phase-01/p1-t3-batch-analysis-and-enrichment.md) | Add AI dedupe, clustering, gap analysis, and item-enrichment behaviors. |

## Dependencies

- The current backlog CRUD, chat, and apply flows must remain stable.
- The LLM routing path used by content-gen agents must remain available for new triage prompts.

## Exit Criteria

- A superuser can request backlog triage on the existing backlog workspace and receive structured batch proposals.
- Proposed changes are reviewable before apply and persist only through validated service methods.
- The AI can enrich sparse backlog items and identify duplicates or gaps without bypassing operator approval.
