# Task 025: Rewrite The Executive Summary As Insight-Only

Status: Completed

## Objective

Rewrite the Executive Summary so it presents only research results and reads
like an insight report rather than a process note.

## Problem Statement

The current summary repeats the user prompt, mentions how the analysis was
performed, and uses documentation-style phrasing for gaps. In the harness
report this makes page 1 feel like tooling output instead of a readable
briefing.

## Scope

- synthesize the Executive Summary from findings, themes, and high-level
  implications rather than from the original prompt
- remove process language such as prompt restatement and methodology chatter
- replace long gap wording with a short pointer to the dedicated gaps section
  when that section exists
- enforce a deterministic size budget such as at most two short paragraphs and
  a hard character cap

Out of scope:

- adding a Writer or Editor post-processing stage
- redesigning the Detailed Analysis section
- PDF CSS or pagination changes

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/reporter.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_reporter.py`

## Dependencies

- [020_executive_summary_density_cleanup.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/020_executive_summary_density_cleanup.md)
- [024_report_summary_contract_consolidation.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/024_report_summary_contract_consolidation.md)

## Acceptance Criteria

- the Executive Summary does not include `This research investigated`
- the Executive Summary does not include `Analysis was performed`
- the Executive Summary does not include `Areas requiring additional investigation include`
- when research gaps exist, the summary uses at most a brief pointer to the
  later gaps section instead of listing the gap inventory inline
- the summary stays within the configured paragraph and character budget

## Suggested Verification

- add tests for banned boilerplate phrases and gap-pointer behavior
- run `uv run pytest tests/test_reporter.py`

## Notes For The Implementer

- Favor deterministic truncation and section budgeting over fuzzy summarization.
- Keep the tone direct and readable; the summary should sound like a briefing,
  not a system log.
