# P3-T3 - Add Early Fact-Risk And Uncertainty Gate

## Objective

Stop unsupported ideas before drafting and define the cases where publishing with known uncertainty is acceptable.

## Scope

- classify claims as supported, weak, missing, disputed, or acceptable-with-disclosure
- define hold and kill thresholds before script creation
- document when an operator can proceed with known uncertainty and what disclosure is required

## Affected Areas

- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/agents/qc.py`
- `docs/content-generation.md`
- `docs/content-gen-artifact.md`

## Dependencies

- P3-T2 must produce a thesis artifact tied to claim status

## Acceptance Criteria

- unsupported ideas can be held or killed before drafting
- known-uncertainty publish rules are explicit and auditable
- final QC no longer performs the first meaningful fact-risk decision
