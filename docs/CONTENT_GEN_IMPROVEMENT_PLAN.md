# Content Generation Improvement Plan

This document turns the current content-generation workflow into a faster operating system for a lean team.

The current 14-stage design is still useful as a reference architecture, but it is too artifact-heavy and too linear to be the primary operating model. This plan compresses the workflow into seven decision-heavy phases, adds explicit gates, and makes reuse, cost control, and feedback loops first-class behavior.

## Design Goals

- reduce cycle time without losing traceability
- move kill decisions earlier
- branch by content type and effort tier
- let packaging and channel format shape the draft sooner
- start fact and brand risk checks before final QC
- make repurposing a standard output, not an afterthought
- feed performance learnings back into the next run continuously

## Mandatory Phase Fields

Every operating phase introduced by this plan should define:

- owner
- max turnaround time
- entry criteria
- exit criteria
- skip conditions
- kill conditions
- reuse opportunities

These fields should live in typed workflow models and appear in stage traces, managed briefs, and operator-facing docs.

## Implementation Principles

- Keep the existing stage contracts working while introducing a seven-phase view.
- Preserve `StageTrace`, `ClaimLedger`, and `PipelineContext`, but make them support faster decisions rather than extra paperwork.
- Prefer grouped operating phases over adding more standalone artifacts.
- Treat performance review as an always-on rule update loop, not a once-per-cycle appendix.

## Phase Roadmap

| Phase | Focus | Outcome |
| --- | --- | --- |
| [Phase 01](phases/phase-01-strategy-and-constraints.md) | Strategy and constraints | Operators start with a constrained brief and explicit workflow rules instead of an open-ended setup stage. |
| [Phase 02](phases/phase-02-opportunity-and-idea-scoring.md) | Opportunity and idea scoring | Low-value ideas are killed early and work is capped by ROI, effort, and content type. |
| [Phase 03](phases/phase-03-research-and-argument.md) | Research and argument | Research depth matches upside and fact risk, and weak evidence can stop production before drafting. |
| [Phase 04](phases/phase-04-draft-and-packaging.md) | Draft and packaging | Script and packaging are developed together so the channel format shapes the content early. |
| [Phase 05](phases/phase-05-visual-and-production-brief.md) | Visual and production brief | Only viable drafts receive right-sized execution planning for their actual format. |
| [Phase 06](phases/phase-06-qc-and-publish.md) | QC and publish | QC becomes progressive, and final approval is a fast publish decision with explicit risk states. |
| [Phase 07](phases/phase-07-performance-and-rule-updates.md) | Performance and rule updates | Learnings update scoring, hooks, packaging, and reuse rules continuously. |

## Delivery Sequence

Start with Phase 01 through Phase 03 before broad prompt or CLI expansion. Those phases establish the operating contract, gating model, and evidence rules that later phases depend on.

Phase 04 through Phase 06 should focus on reducing handoff friction and collapsing late-stage overhead. Phase 07 should land before the new operating model is declared complete, otherwise the workflow will still learn too slowly.
