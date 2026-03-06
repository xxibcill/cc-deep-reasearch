# Task 012: Strengthen Report Evidence Annotations

## Objective

Make reports communicate strength, freshness, and uncertainty of findings instead of presenting all findings with the same confidence.

## Scope

- add report markers or sections for:
  - evidence strength
  - contradiction notes
  - freshness notes
  - primary-source coverage
- include iteration summary when follow-up search materially changed results
- extend JSON report output with claims, evidence strength, unresolved gaps, and validation rationale

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/reporter.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/reporting.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_reporter.py`

## Dependencies

- [009_claim_evidence_model.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/009_claim_evidence_model.md)
- [010_validator_failure_modes.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/010_validator_failure_modes.md)

## Acceptance Criteria

- readers can identify strong, weak, and contested findings
- JSON output exposes evidence-oriented fields for downstream tooling
- report tests validate the new structure

## Suggested Verification

- run `pytest tests/test_reporter.py`
