# Task 010: Make Validation Failure Modes Evidence-Aware

Status: Done

## Objective

Teach the validator to distinguish between insufficient quantity and insufficient quality of evidence.

## Scope

- add scores for:
  - freshness fitness
  - primary-source coverage
  - claim support density
  - contradiction pressure
  - source-type diversity
- produce targeted follow-up recommendations
- distinguish “needs more sources” from “needs better sources”

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/validator.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestrator.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/models.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_validator.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_orchestrator.py`

## Dependencies

- [007_source_provenance_tracking.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/007_source_provenance_tracking.md)
- [009_claim_evidence_model.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/009_claim_evidence_model.md)

## Acceptance Criteria

- validation output names specific failure modes
- follow-up query generation can react to those failure modes
- tests cover at least one contradiction-heavy case and one weak-primary-source case

## Suggested Verification

- run `pytest tests/test_validator.py tests/test_orchestrator.py`

## Completion Notes

- Completed on 2026-03-07
- Validation output now reports named failure modes, evidence-quality scores, and a quantity-vs-quality diagnosis
- Follow-up query generation reacts to validation failure modes
- Verified with `pytest tests/test_validator.py tests/test_orchestrator.py`
