# P3-T1 - Route Research Depth By Upside And Risk

## Objective

Match research time and validation depth to the expected upside and fact risk of the idea.

## Scope

- define depth tiers for low, medium, and high research investment
- route search budget, source requirements, and validation effort from scoring outputs
- preserve an operator override path for exceptional ideas

## Affected Areas

- `src/cc_deep_research/content_gen/agents/research_pack.py`
- `src/cc_deep_research/config/schema.py`
- `src/cc_deep_research/content_gen/models.py`
- `docs/content-generation.md`

## Dependencies

- Phase 02 must produce effort tier and expected upside

## Acceptance Criteria

- research depth is explicit before the first query is generated
- time and search budgets vary by tier instead of staying flat
- traces show when an operator used an override
