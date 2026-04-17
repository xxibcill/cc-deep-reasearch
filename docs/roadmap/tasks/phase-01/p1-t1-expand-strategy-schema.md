# P1-T1 - Expand Strategy Schema

## Status

Done. Added `ContentPillar`, `PlatformRule`, `CTAStrategy`, `ClaimToProofRule` models. Added `positioning`, `business_objective`, `allowed_audience_universe`, `forbidden_topics`, `cta_strategy`, `claim_to_proof_rules`, `platform_rules` fields to `StrategyMemory`. Changed `content_pillars` from `list[str]` to `list[ContentPillar]` with backward-compatible string coercion validator.

## Summary

Expand the backend strategy model so it can represent the full outer-layer concepts described in the strategy guide.

## Scope

- Add missing global fields such as `positioning`, `business_objective`, `allowed_audience_universe`, `forbidden_topics`, `cta_strategy`, and `claim_to_proof_rules`.
- Introduce structured models for `ContentPillar`, platform rules, CTA policy, and claim-to-proof mappings.
- Preserve existing fields like `proof_rules`, `contrarian_beliefs`, `audience_segments`, and `performance_guidance`.

## Deliverables

- Updated Pydantic models in `src/cc_deep_research/content_gen/models.py`
- Field-level validators and coercion for legacy string-list inputs where reasonable
- Updated model serialization coverage in tests

## Dependencies

- Target field set from `docs/improve-strategy-guide.md`

## Acceptance Criteria

- Strategy can express identity, boundaries, proof policy, audience universe, platform rules, and CTA rules without overloading string arrays.
- The schema is explicit enough for a structured dashboard editor to consume directly.
