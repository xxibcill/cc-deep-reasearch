# P3-T2 - Upgrade Learning Payloads

## Summary

Replace vague learning summaries with structured learning records that are specific enough to justify promotion and reuse.

## Scope

- Add fields for exact pattern, platform, content type, audience context, source IDs, evidence count, baseline comparison, confidence, and review dates.
- Preserve compatibility for existing learning records where feasible.
- Update extraction and serialization flows to support richer learning payloads.

## Deliverables

- Upgraded learning model and persistence
- Updated learning extraction logic
- Regression tests for structured learnings

## Dependencies

- Phase 01 schema work

## Acceptance Criteria

- Promoted learnings are concrete and auditable.
- Learning records contain enough context to distinguish one-off observations from reusable guidance.
