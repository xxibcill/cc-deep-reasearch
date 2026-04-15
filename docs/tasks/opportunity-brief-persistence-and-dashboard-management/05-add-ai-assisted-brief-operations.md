# Phase 05 - Add AI-Assisted Brief Operations

## Functional Feature Outcome

Operators can use AI to refine and operationalize opportunity briefs while keeping all persistent changes behind explicit apply flows.

## Why This Phase Exists

Brief management will quickly become cumbersome if every refinement must be done manually, but letting AI write directly into persistent state would undermine trust. This phase mirrors the backlog model: advisory AI endpoints generate proposals, operators review them, and accepted changes are applied explicitly. It also formalizes the handoff from approved brief to backlog generation so the brief becomes an active editorial planning hub.

## Scope

- Add conversational and structured AI-assisted refinement flows for briefs.
- Add explicit brief-to-backlog handoff and apply semantics grounded in an approved brief.
- Support comparison, reuse, and branching workflows so operators can iterate without losing history.

## Tasks

| Task | Summary |
| --- | --- |
| [P5-T1](./p5-t1-brief-assistant-workspace.md) | Add AI-assisted brief refinement with advisory responses and explicit apply routes. |
| [P5-T2](./p5-t2-brief-to-backlog-apply-flow.md) | Turn approved briefs into deliberate backlog-generation and apply workflows. |
| [P5-T3](./p5-t3-brief-reuse-compare-and-branching.md) | Support comparison, reuse, and branching of briefs for editorial experimentation. |

## Dependencies

- Phase 04 should already expose the brief workspace operators use to review proposals.
- Backlog persistence and mutation patterns should remain the source of truth for backlog-side apply behavior.

## Exit Criteria

- AI can propose brief changes without silently mutating persisted state.
- Operators can generate and apply backlog work from a chosen approved brief version.
- Brief comparison and reuse workflows preserve traceability instead of encouraging overwrite-in-place editing.
