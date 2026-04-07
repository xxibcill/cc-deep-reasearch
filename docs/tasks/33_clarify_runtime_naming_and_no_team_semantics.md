# Task 33: Clarify Runtime Naming and `--no-team` Semantics

**Status: Done**

## Goal

Make code and docs tell the truth about local execution versus future multi-agent ambitions.

## Scope

- review user-facing help and docs for misleading team or agent wording
- ensure `--no-team` behavior is documented consistently
- rename only obviously misleading comments or labels if the code behavior stays local

## Primary Files

- `src/cc_deep_research/cli/research.py`
- `README.md`
- `docs/USAGE.md`
- `docs/RESEARCH_WORKFLOW.md`

## Acceptance Criteria

- docs and CLI help agree on what `--no-team` actually does
- no user-facing text implies a distributed runtime that does not exist

## Validation

- `uv run pytest tests/test_cli_research.py -v` - passed
