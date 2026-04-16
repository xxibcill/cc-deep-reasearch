# P2-T3 - Add Content-Type Branching Profiles

## Status

Done.

Implemented:
- `ContentTypeProfile` dataclass added to `models.py` with research/drafting/production/packaging depth per profile type
- `ScoringOutput` gains `content_type_profile` field — set from `RunConstraints.content_type` at scoring time so selected ideas carry their profile before research starts
- `PipelineCandidate` gains optional `content_type_profile` field so each lane preserves its profile through the pipeline
- Profile is derived from `RunConstraints.content_type` at pipeline start, validated against known profile keys
- `docs/content-generation.md` Stage 3 section updated to describe how scoring now carries content-type profile into downstream stages
- `docs/content-gen-workflow-template.md` updated with profile column and branching behavior per content type

## Objective

Make the workflow branch by asset type so shorts, newsletters, articles, webinars, and launch assets do not all require the same depth.

## Scope

- define content-type profiles with default research, drafting, production, and packaging depth
- apply profile selection during opportunity scoring, not after drafting begins
- document which artifacts are required, optional, or skipped for each profile

## Affected Areas

- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/cli.py`
- `docs/content-gen-workflow-template.md`
- `docs/content-generation.md`

## Dependencies

- P1-T3 must expose content type as a run-level constraint

## Acceptance Criteria

- a selected idea carries a content-type profile before research starts
- skip conditions differ by profile and are visible in docs and traces
- the workflow no longer assumes one default depth for all asset classes
