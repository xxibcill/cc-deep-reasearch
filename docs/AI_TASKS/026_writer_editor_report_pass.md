# Task 026: Add A Writer Editor Pass To The Report Pipeline

Status: Completed

## Objective

Introduce a dedicated Writer or Editor stage that rewrites the first draft of
the report for readability before the final output is returned.

## Problem Statement

The repo already has report-quality evaluation and a refiner component, but the
active markdown report pipeline still returns the raw first draft. That leaves
no explicit stage responsible for turning a technically correct report into a
good reading experience.

## Scope

- define one component as the post-draft Writer or Editor stage
- run that stage inside the markdown report pipeline after the initial draft is
  produced
- preserve section structure, findings, and citations while improving wording
  and flow
- add a focused test that proves the rewrite stage is invoked

Out of scope:

- changing the research-analysis phase itself
- generating new findings or new sources during report rewriting
- PDF rendering changes

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/reporting.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/report_refiner.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/__init__.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_reporter.py`

## Dependencies

- [024_report_summary_contract_consolidation.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/024_report_summary_contract_consolidation.md)

## Acceptance Criteria

- `ReportGenerator.generate_markdown_report()` invokes a dedicated rewrite stage
  after the initial markdown draft is created
- the rewrite stage preserves required report sections and existing citations
- the report pipeline no longer stops at evaluation-only behavior when a rewrite
  stage is configured
- tests verify the rewrite stage runs and its output is returned

## Suggested Verification

- add one focused pipeline test that stubs or observes the rewrite stage
- run `uv run pytest tests/test_reporter.py`

## Notes For The Implementer

- Prefer reusing the existing refiner path if it can cleanly own the Writer or
  Editor responsibility.
- Keep this task about pipeline integration, not about inventing a large new
  prompt framework.
