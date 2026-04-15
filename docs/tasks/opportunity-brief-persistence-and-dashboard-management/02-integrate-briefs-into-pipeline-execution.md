# Phase 02 - Integrate Briefs Into Pipeline Execution

## Functional Feature Outcome

Pipeline runs can deliberately reference, resume from, and enforce approved versions of persistent opportunity briefs.

## Why This Phase Exists

Persistent storage alone is not enough. If the pipeline still treats the brief as an incidental stage output, operators will have no reliable way to trust which version downstream work used. This phase makes the brief a controlled handoff artifact between planning and execution, ensures resumed runs keep that linkage, and adds explicit gates so downstream automation can use approved brief versions intentionally.

## Scope

- Reference persisted brief identity and revision metadata from `PipelineContext` and saved jobs.
- Add execution gates so operators can choose whether downstream work requires an approved brief.
- Support resume, clone, and seeded-run flows that start from a selected brief version.

## Tasks

| Task | Summary |
| --- | --- |
| [P2-T1](./p2-t1-pipeline-context-reference-model.md) | Teach pipeline state to reference a managed brief resource and revision, not only inline brief payloads. |
| [P2-T2](./p2-t2-approved-brief-execution-gates.md) | Add approval-aware downstream gates and execution semantics. |
| [P2-T3](./p2-t3-resume-clone-and-seeded-run-flows.md) | Support resume, clone, and start-from-brief workflows with stable provenance. |

## Dependencies

- Phase 01 must define the persistent brief identifiers, lifecycle, and storage APIs.
- Orchestrator and pipeline-run persistence must tolerate mixed old and new state during rollout.

## Exit Criteria

- Pipeline runs can point to a specific brief and revision unambiguously.
- Operators can start or resume execution from a saved brief deliberately.
- Downstream stages can distinguish draft, edited, and approved brief usage.
