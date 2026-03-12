# Task 023: Add Readability Regression Tests For PDF Reports

Status: Planned

## Objective

Lock the readability work in place with tests that verify report structure and
section-aware PDF behavior without depending on fragile binary PDF snapshots.

## Problem Statement

The readability changes in tasks `018` through `022` touch both report content
and PDF rendering hooks. Without explicit tests, later edits could easily remove
section wrappers, re-expand the executive summary, or collapse the Sources
section back into a dominant monolith.

## Scope

- add focused unit tests for the new HTML wrapper structure
- add tests for compact executive-summary behavior
- add tests for the Sources summary/catalog split
- add tests that assert appendix and typography selectors are present in the CSS

Out of scope:

- pixel-perfect PDF snapshot testing
- end-to-end browser or GUI automation
- broader reporter behavior unrelated to readability work

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_markdown_to_pdf.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_reporter.py`

## Dependencies

- [018_pdf_section_wrappers.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/018_pdf_section_wrappers.md)
- [019_pdf_section_typography.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/019_pdf_section_typography.md)
- [020_executive_summary_density_cleanup.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/020_executive_summary_density_cleanup.md)
- [021_sources_summary_and_catalog_split.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/021_sources_summary_and_catalog_split.md)
- [022_appendix_deemphasis_and_pagination.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/022_appendix_deemphasis_and_pagination.md)

## Acceptance Criteria

- tests fail if section wrappers disappear from the generated HTML
- tests fail if the Executive Summary inlines full gap inventories again
- tests fail if the Sources section loses either its compact summary or full catalog marker
- tests fail if appendix-related CSS selectors or page-break rules are removed
- the verification commands for the touched test files pass

## Suggested Verification

- run `uv run pytest tests/test_markdown_to_pdf.py tests/test_reporter.py`

## Notes For The Implementer

- Prefer direct string or structure assertions over brittle full-document fixtures.
- Keep the tests narrowly focused on the readability contract introduced by this task pack.
