# P6-T1 - Add Progressive QC Checkpoints

## Objective

Move quality control earlier so final QC is a release gate, not the first serious review of facts, brand fit, or format issues.

## Scope

- define lightweight QC checks in research, draft, and execution phases
- surface claim, brand, and packaging issues before the final stage
- keep final QC focused on release readiness and unresolved exceptions

## Affected Areas

- `src/cc_deep_research/content_gen/agents/qc.py`
- `src/cc_deep_research/content_gen/orchestrator.py`
- `src/cc_deep_research/content_gen/models.py`
- `docs/content-generation.md`

## Dependencies

- earlier phases must expose claim status, uncertainty, and content-type metadata

## Acceptance Criteria

- basic fact and brand issues can be caught before late-stage QC
- final QC operates on a reduced fix list
- stage traces show where an issue first appeared
