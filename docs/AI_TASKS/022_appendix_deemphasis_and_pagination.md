# Task 022: De-Emphasize Appendix Sections In The PDF

Status: Planned

## Objective

Treat Sources and Research Metadata as appendix material in the PDF so they stay
available without competing with the main report narrative.

## Problem Statement

Even after section-specific typography is added, appendix-like sections still
need stronger layout cues. Sources and metadata should feel quieter, denser, and
more separate from the analytical sections.

This task should focus on appendix presentation only.

## Scope

- start the full source catalog on a fresh page
- give source-catalog content a smaller, quieter visual treatment
- give Research Metadata compact appendix styling and a clean page break
- add page-break safeguards so headings are less likely to orphan at the bottom of a page

Out of scope:

- changing which sources are included
- changing executive-summary or findings content
- snapshot-testing the exact PDF rendering

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/pdf_generator.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_markdown_to_pdf.py`

## Dependencies

- [019_pdf_section_typography.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/019_pdf_section_typography.md)
- [021_sources_summary_and_catalog_split.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/021_sources_summary_and_catalog_split.md)

## Acceptance Criteria

- the full source catalog begins on a fresh page or appendix boundary in the PDF stylesheet
- Sources and Research Metadata use compact appendix styling that is visibly quieter than the main analysis sections
- top-level and subsection headings gain basic page-break protection
- the PDF still renders successfully for reports that do not contain every optional section

## Suggested Verification

- add tests that assert appendix-related CSS selectors and page-break rules are present
- generate a sample PDF and inspect the transition into the Sources and Research Metadata pages
- run `uv run pytest tests/test_markdown_to_pdf.py`

## Notes For The Implementer

- This task should build on the structure from `021`, not replace it.
- Use modest CSS changes; the goal is de-emphasis, not an entirely different template.
