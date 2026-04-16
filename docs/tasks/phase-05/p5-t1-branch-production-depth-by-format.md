# P5-T1 - Branch Production Depth By Format

## Objective

Prevent simple assets from inheriting the full planning burden of more complex production formats.

## Scope

- define production complexity classes such as low, medium, and high
- map each content-type profile to the minimum visual and production work required
- make skip conditions explicit for low-complexity assets

## Affected Areas

- `src/cc_deep_research/content_gen/agents/visual.py`
- `src/cc_deep_research/content_gen/agents/production.py`
- `src/cc_deep_research/content_gen/models.py`
- `docs/content-generation.md`

## Dependencies

- Phase 02 content-type profiles and Phase 04 draft package decisions

## Acceptance Criteria

- low-complexity formats can skip heavy production planning without losing clarity
- planning depth is derived from profile and execution complexity
- traces show why a format took the light or heavy path
