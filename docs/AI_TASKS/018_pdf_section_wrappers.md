# Task 018: Add Section-Aware PDF Wrappers

Status: Planned

## Objective

Make the PDF HTML output section-aware so later styling work can target each
major report section without brittle heading-only CSS.

## Problem Statement

The current markdown-to-PDF path converts markdown directly to flat HTML in
[`src/cc_deep_research/pdf_generator.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/pdf_generator.py).
That output has no semantic wrappers for sections such as Executive Summary,
Detailed Analysis, Sources, or Research Metadata.

As a result:

- CSS can only style generic `h1`, `h2`, `h3`, `p`, and list elements
- section-specific font choices are awkward or impossible
- appendix sections such as Sources cannot be cleanly de-emphasized
- later layout work would have to depend on fragile text matching in CSS

## Scope

- add a small HTML post-processing step after markdown conversion
- wrap each top-level report section in a semantic container with stable classes
- include a generic fallback class for unknown sections
- keep the existing markdown content and section order unchanged

Out of scope:

- visual redesign of fonts, spacing, or colors
- report content changes
- source appendix restructuring

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/pdf_generator.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_markdown_to_pdf.py`

## Dependencies

None.

## Acceptance Criteria

- HTML generated for the PDF contains one wrapper per major section
- wrappers include both a common class and a section-specific class
- at minimum, the following sections are distinguishable when present:
  - title block
  - Executive Summary
  - Methodology
  - Key Findings
  - Detailed Analysis
  - Sources
  - Research Metadata
- unknown section headings fall back to a stable generic class rather than being skipped
- existing markdown-to-PDF behavior still succeeds for basic input

## Suggested Verification

- add or update unit tests that inspect the generated HTML string rather than the binary PDF
- run `uv run pytest tests/test_markdown_to_pdf.py`

## Notes For The Implementer

- Keep the wrapper logic simple and deterministic.
- Prefer a dedicated helper method over inline string manipulation in `_convert_to_html()`.
- Do not couple the wrapper logic to one specific report template beyond the section names already emitted by the repo.
