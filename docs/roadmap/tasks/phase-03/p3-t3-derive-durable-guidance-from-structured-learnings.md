# P3-T3 - Derive Durable Guidance From Structured Learnings

## Summary

Promote structured learnings into durable strategy guidance without losing compatibility with the current `performance_guidance` layer.

## Scope

- Define promotion mapping from learning records into durable strategy rules and heuristics.
- Keep legacy `performance_guidance` fields available while richer rules become the primary source of truth.
- Preserve traceability from durable guidance back to learning and content evidence.

## Deliverables

- Promotion logic for structured learnings
- Backward-compatible durable guidance output
- Tests for promotion and traceability

## Dependencies

- P3-T2 structured learning payloads

## Acceptance Criteria

- Durable strategy guidance can be explained in terms of source learnings and source content.
- The product can continue using legacy guidance fields during migration.
