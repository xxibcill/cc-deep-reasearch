# Task 028: Regenerate The Harness Report Fixtures

Status: Completed

## Objective

Refresh the harness markdown and PDF fixtures so they reflect the new report
writing contract and provide a visible verification artifact.

## Problem Statement

The current harness fixtures still show the old Executive Summary shape. Once
the summary and Writer or Editor pipeline changes land, those sample outputs
will be misleading unless they are regenerated.

## Scope

- regenerate the harness markdown report using the updated report pipeline
- regenerate the harness PDF from the updated markdown
- verify that the refreshed fixtures reflect the new Executive Summary contract
  and page-1 readability goals

Out of scope:

- changing the underlying research corpus or query
- adding brittle binary PDF snapshot tests
- broader documentation rewrites outside the fixture outputs

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/harness.md`
- `/Users/jjae/Documents/guthib/cc-deep-research/harness_report.pdf`

## Dependencies

- [025_executive_summary_insight_only_rewrite.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/025_executive_summary_insight_only_rewrite.md)
- [026_writer_editor_report_pass.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/026_writer_editor_report_pass.md)
- [027_executive_summary_quality_guardrails.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/027_executive_summary_quality_guardrails.md)

## Acceptance Criteria

- `harness.md` reflects the new summary wording contract
- `harness_report.pdf` no longer includes the prompt restatement, method
  explanation, or full gap inventory dump in the Executive Summary
- the Executive Summary fits within a single PDF page and does not spill into a
  multi-page summary block

## Suggested Verification

- regenerate both fixture files with the updated report pipeline
- manually inspect page 1 of the PDF
- run `uv run pytest tests/test_reporter.py tests/test_report_quality_evaluator.py tests/test_markdown_to_pdf.py`

## Notes For The Implementer

- Treat this as a fixture refresh task after the code changes land.
- Keep the verification lightweight; manual PDF inspection is acceptable here.
