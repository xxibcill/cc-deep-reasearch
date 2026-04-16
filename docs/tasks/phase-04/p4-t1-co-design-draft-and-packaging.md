# P4-T1 - Co-Design Draft And Packaging

## Objective

Make hooks, titles, CTAs, and channel format shape the draft from the start instead of after the script is already fixed.

## Scope

- join scripting and packaging inputs earlier in the flow
- define a draft package that carries hook options, core draft, CTA, and channel packaging together
- keep early packaging variants lightweight enough for fast iteration

## Affected Areas

- `src/cc_deep_research/content_gen/agents/scripting.py`
- `src/cc_deep_research/content_gen/agents/packaging.py`
- `src/cc_deep_research/content_gen/models.py`
- `docs/scripting.md`

## Dependencies

- Phase 03 must provide approved thesis and uncertainty status

## Acceptance Criteria

- packaging signals influence the draft before visual planning
- channel mismatch is caught in the draft lane rather than late packaging
- one review surface can show the draft and its primary packaging options together
