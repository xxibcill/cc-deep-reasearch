# P6-T2 - Merge Approval With Publish Readiness

## Objective

Replace the current stop-before-publish default with an explicit release-state model that supports blocked, approved, and approved-with-known-risks outcomes.

## Scope

- define release states and their transition rules
- connect approval state directly to publish queue preparation
- document the minimum data required to create a publish-ready package

## Affected Areas

- `src/cc_deep_research/content_gen/agents/publish.py`
- `src/cc_deep_research/content_gen/agents/qc.py`
- `src/cc_deep_research/content_gen/storage/publish_queue.py`
- `docs/content-generation.md`

## Dependencies

- P6-T1 must establish progressive QC inputs

## Acceptance Criteria

- assets can enter the publish queue only through an explicit release state
- approved-with-known-risks has documented constraints and disclosure rules
- the default workflow no longer stops before publish without a clear decision model
