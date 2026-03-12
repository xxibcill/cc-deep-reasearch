# Task 021: Split Sources Into Summary And Catalog

Status: Planned

## Objective

Make the Sources section easier to navigate by separating a short summary view
from the full catalog, without dropping any citations.

## Problem Statement

The current Sources section is effectively one long catalog. In large reports it
can consume nearly half the PDF, which makes references feel as prominent as the
analysis itself.

Before the appendix can be visually de-emphasized, the content needs a clearer
shape.

## Scope

- keep a short summary at the top of the Sources section
- add a clearly labeled full catalog subsection after that summary
- preserve complete source coverage and existing credibility grouping
- keep the implementation within the existing markdown report format

Out of scope:

- PDF page-break rules for the appendix
- global typography changes
- dropping sources from the final report

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/reporter.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_reporter.py`

## Dependencies

- [018_pdf_section_wrappers.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/018_pdf_section_wrappers.md)

## Acceptance Criteria

- the Sources section opens with a compact summary block rather than jumping straight into the full catalog
- the full source listing still appears in the report under an explicitly labeled subsection such as `Full Catalog`
- credibility distribution information remains available
- every source that was previously listed still appears somewhere in the final report

## Suggested Verification

- add tests that assert both the summary marker and full catalog marker are present
- add a test that checks all mocked sources still render into the catalog
- run `uv run pytest tests/test_reporter.py`

## Notes For The Implementer

- Keep the summary short and structural.
- Do not invent a ranking algorithm beyond what the repo already exposes for credibility scoring.
- Avoid changing source ordering unless the test updates are deliberate and justified.
