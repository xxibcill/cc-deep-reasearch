# Task 027: Add Executive Summary Quality Guardrails

Status: Completed

## Objective

Teach the quality gate to detect Executive Summary regressions so boilerplate
wording and oversized summaries do not quietly return.

## Problem Statement

Even if the summary and rewrite stages are cleaned up, later edits could easily
reintroduce prompt restatement, methodology chatter, or inline gap inventories.
The current report-quality checks do not explicitly guard against those
patterns.

## Scope

- inspect the Executive Summary as a distinct section during report-quality
  evaluation
- add deterministic checks for banned boilerplate phrases
- add deterministic checks for summary length over the configured budget
- flag inline gap inventories in the summary while allowing a short pointer to
  the gaps section

Out of scope:

- rewriting the summary generation itself
- redesigning the broader quality scoring model
- PDF rendering tests

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/report_quality_evaluator.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_report_quality_evaluator.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_reporter.py`

## Dependencies

- [024_report_summary_contract_consolidation.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/024_report_summary_contract_consolidation.md)
- [025_executive_summary_insight_only_rewrite.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/025_executive_summary_insight_only_rewrite.md)

## Acceptance Criteria

- a summary that repeats the prompt or mentions the analysis method triggers a
  warning or issue
- a summary that exceeds the configured size budget triggers a warning or issue
- a summary that dumps the full gap inventory inline triggers a warning or issue
- a compliant insight-only summary does not trigger those specific guardrails

## Suggested Verification

- add evaluator tests using both a bad harness-style summary and a compliant
  summary
- run `uv run pytest tests/test_report_quality_evaluator.py tests/test_reporter.py`

## Notes For The Implementer

- Keep the checks deterministic and section-aware.
- Prefer tight string and length assertions over subjective writing judgments.
