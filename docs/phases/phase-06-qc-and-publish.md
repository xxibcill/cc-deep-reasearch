# Phase 06 - QC And Publish

## Functional Feature Outcome

Quality control becomes progressive and the final release gate produces an explicit publish state with auditable risk handling.

## Why This Phase Exists

The current workflow defers too much quality checking to late-stage QC and then still requires a separate approval step to publish. This phase moves fact and brand checks earlier, shortens the final gate, and turns publish readiness into a clear operational decision instead of a delayed appendix.

## Scope

- add progressive QC checkpoints before final review
- merge approval and publish preparation into one release lane
- record overrides, known risks, and audit history for every published asset

## Tasks

| Task | Summary |
| --- | --- |
| [P6-T1](../tasks/phase-06/p6-t1-add-progressive-qc-checkpoints.md) | Move fact, brand, and formatting checks earlier in the workflow. |
| [P6-T2](../tasks/phase-06/p6-t2-merge-approval-with-publish-readiness.md) | Replace the current stop-before-publish behavior with a true release-state model. |
| [P6-T3](../tasks/phase-06/p6-t3-record-human-overrides-and-audit-trail.md) | Persist operator overrides, risk acknowledgements, and approval history. |

## Dependencies

- earlier phases must expose claim status, uncertainty, content type, and execution readiness
- publish queue and managed brief persistence should be extended rather than replaced

## Exit Criteria

- no asset reaches publish without an explicit blocked, approved, or approved-with-known-risks state
- late-stage QC is focused on release readiness instead of rediscovering basic fact or brand issues
- publish queue entries include the decision history needed for audit and postmortem review
