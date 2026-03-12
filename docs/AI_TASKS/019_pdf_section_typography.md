# Task 019: Apply Section-Specific PDF Typography

Status: Planned

## Objective

Use the new section wrappers to give each report section a clearer typographic
role, with long-form reading sections, utility sections, and appendix sections
visibly separated.

## Problem Statement

The current PDF stylesheet applies one visual voice to nearly the entire report.
Body copy is justified, headings are visually similar across sections, and
appendix content such as Sources and Research Metadata feels almost as important
as the actual analysis.

The first pass should fix the typography only, without mixing in larger content
or source-structure changes.

## Scope

- update the PDF CSS to use distinct font stacks by section
- keep long-form sections easier to read than utility sections
- remove or relax fully justified body text
- improve spacing between headings, paragraphs, and lists
- keep the design dependent only on built-in font stacks that work in WeasyPrint

Out of scope:

- changing report wording or summary length
- splitting the Sources section into summary versus full catalog
- adding PDF snapshot tests

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/pdf_generator.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_markdown_to_pdf.py`

## Dependencies

- [018_pdf_section_wrappers.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/018_pdf_section_wrappers.md)

## Acceptance Criteria

- Executive Summary and Detailed Analysis use a different body font stack from Sources and Research Metadata
- headings remain sans-serif and visually stronger than body text
- normal body paragraphs are left-aligned or otherwise no longer fully justified
- list spacing and paragraph spacing are tuned so dense sections are easier to scan
- Sources and Research Metadata have visibly lighter, smaller, or quieter typography than the main analysis sections

## Suggested Verification

- add lightweight tests that assert the CSS includes the expected section selectors
- generate a sample PDF locally and inspect at least the first page, one analysis page, and one sources page
- run `uv run pytest tests/test_markdown_to_pdf.py`

## Notes For The Implementer

- Keep this task CSS-only once the wrappers exist.
- Favor boring, reliable font stacks such as Georgia for long-form text and system sans stacks for headings and appendix sections.
- Resist adding decorative colors or layout flourishes in this task.
