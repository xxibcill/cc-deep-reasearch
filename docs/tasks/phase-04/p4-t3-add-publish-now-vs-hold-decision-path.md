# P4-T3 - Add Publish-Now Vs Hold Decision Path

## Objective

Let operators decide whether an asset should move forward quickly, wait for stronger proof, or return to the backlog without forcing one default path.

## Scope

- define draft-lane decisions for publish now, hold for proof, recycle for reuse, and kill
- carry uncertainty and risk status into the decision
- document the minimum package needed to publish quickly without skipping auditability

## Affected Areas

- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/orchestrator.py`
- `docs/content-generation.md`
- `docs/brief-management.md`

## Dependencies

- P3-T3 must define acceptable uncertainty states

## Acceptance Criteria

- the workflow can stop or publish from the draft lane with an explicit reason
- fast-path publishes still preserve claim status and packaging context
- later stages are only invoked when they add real value for the selected path
