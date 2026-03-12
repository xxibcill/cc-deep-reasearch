# Task 020: Shorten The Executive Summary Layer

Status: Planned

## Objective

Prevent the Executive Summary from turning into a wall of text by limiting it to
a short overview and pushing long gap inventories back into the dedicated gaps
section.

## Problem Statement

The current report generator can inline too much material into the Executive
Summary, especially when there are many research gaps. In the observed harness
report, page 1 is dominated by one dense summary block before the reader reaches
the Key Findings.

This task should improve the content shape, not the PDF styling.

## Scope

- tighten the Executive Summary generation logic in the reporter
- keep the summary focused on query, source count, major themes, and high-level takeaway
- replace long embedded gap lists with a short pointer to the Research Gaps section
- preserve the full gaps content in the later section

Out of scope:

- redesigning Key Findings or Detailed Analysis
- changing source rendering
- PDF CSS changes

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/reporter.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_reporter.py`

## Dependencies

None.

## Acceptance Criteria

- Executive Summary no longer prints the full research-gap inventory inline
- when gaps exist, the summary uses at most a short sentence that points readers to the dedicated gaps section
- the Research Gaps and Limitations section still includes the full gap descriptions and suggested follow-up queries
- existing report generation still succeeds for sessions with and without gaps

## Suggested Verification

- add tests that cover a session with many gaps and assert the summary remains compact
- run `uv run pytest tests/test_reporter.py`

## Notes For The Implementer

- Prefer deterministic length control over fuzzy heuristics.
- Avoid introducing a generic text summarizer here; the goal is simply to stop the summary from swallowing later sections.
