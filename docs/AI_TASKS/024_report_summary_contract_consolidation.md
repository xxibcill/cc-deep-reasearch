# Task 024: Consolidate Executive Summary Generation

Status: Completed

## Objective

Give the report pipeline one canonical implementation of Executive Summary
generation so later readability changes land in one place.

## Problem Statement

Executive Summary behavior currently exists in more than one code path. That
creates drift risk: a cleanup in one helper can leave another helper still
producing the old boilerplate.

Before changing the wording contract, the implementation surface should be
reduced.

## Scope

- choose one canonical Executive Summary builder for markdown report generation
- remove the duplicate template logic or reduce it to a thin wrapper
- move summary constraints into named constants or helper functions in the
  canonical implementation
- add a focused test that exercises the canonical path

Out of scope:

- rewriting the final Executive Summary prose
- adding a Writer or Editor stage
- PDF styling changes

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/reporter.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/reporting.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_reporter.py`

## Dependencies

- [020_executive_summary_density_cleanup.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/020_executive_summary_density_cleanup.md)

## Acceptance Criteria

- markdown report generation uses one Executive Summary implementation
- the duplicate summary template is deleted or delegates directly to the
  canonical implementation
- summary limits and exclusions are expressed through named constants or helper
  functions rather than scattered literals
- tests cover the canonical summary path used by the report pipeline

## Suggested Verification

- run `uv run pytest tests/test_reporter.py`

## Notes For The Implementer

- Prefer a small refactor over introducing another abstraction layer.
- Keep the public behavior stable in this task; the wording cleanup belongs in
  the follow-up tasks.
