# P2-T3 - Build Structured Editors For Nested Strategy Objects

## Summary

Expose nested strategy records through dedicated editors instead of flattening them into text inputs.

## Scope

- Add editors for audience segments, proof rules, contrarian beliefs, claim-to-proof mappings, platform rules, CTA strategy, and examples.
- Reuse dashboard form primitives where possible.
- Keep small string-list fields as chips or simple lists only when structure is not needed.

## Deliverables

- Nested strategy object editors
- Shared editing primitives for repeated object-list patterns
- UI coverage for the major nested strategy sections

## Dependencies

- P1-T1 schema
- P2-T1 workspace structure

## Acceptance Criteria

- Operators can edit nested strategy objects without using raw JSON.
- The UI reflects the actual structure of the backend models.
