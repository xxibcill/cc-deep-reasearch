# Phase 01 - Strategy And Constraints

## Functional Feature Outcome

Operators can start a content run from a constrained brief with explicit workflow rules, instead of relying on a loose strategy artifact and a mostly linear default pipeline.

## Why This Phase Exists

The current workflow is well documented but not operational enough. It needs a canonical seven-phase view, typed governance fields, and a clear split between evergreen strategy and per-run constraints so teams can move quickly without losing control.

## Scope

- define the compressed seven-phase operating model and map the current 14-stage pipeline into it
- add typed governance fields for owner, SLA, entry and exit criteria, skip conditions, kill conditions, and reuse opportunities
- separate persistent strategy memory from run-specific brief constraints, content type, and effort tier

## Tasks

| Task | Summary |
| --- | --- |
| [P1-T1](../tasks/phase-01/p1-t1-define-compressed-operating-contract.md) | Define the canonical seven-phase operating contract and map the current stage list into it. |
| [P1-T2](../tasks/phase-01/p1-t2-add-operating-policy-metadata.md) | Add typed workflow governance fields and expose them in context and traces. |
| [P1-T3](../tasks/phase-01/p1-t3-split-strategy-from-run-constraints.md) | Separate evergreen strategy memory from per-run constraints and effort controls. |

## Dependencies

- the current content workflow documentation and `PIPELINE_STAGES` registry remain the source of truth for existing behavior
- managed brief persistence and `PipelineContext` should be reused rather than replaced

## Exit Criteria

- every current content-generation stage maps cleanly to one of the seven operating phases
- workflow governance fields exist in typed models and can be surfaced in docs, traces, and managed briefs
- operators can distinguish long-lived strategy from run-specific constraints before idea selection begins
