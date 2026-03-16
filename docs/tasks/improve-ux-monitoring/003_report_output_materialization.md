# Task 003: Extract Report Output Materialization

Status: Planned

## Objective

Separate post-run output handling from orchestration so report rendering, session save, and file writes can be reused outside the CLI.

## Scope

- extract session persistence, markdown/json/html rendering, and optional PDF generation
- return a typed artifact/result object instead of printing directly
- keep terminal rendering out of the shared output helper

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/research_runs/output.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/cli/research.py`

## Dependencies

- [001_shared_research_run_contract.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/001_shared_research_run_contract.md)

## Acceptance Criteria

- report generation and artifact persistence can run without terminal UI dependencies
- output file writes are handled in one shared place
- the CLI can still render or print the final report after the shared helper returns

## Suggested Verification

- run `uv run pytest tests/test_orchestrator.py tests/test_markdown_to_pdf.py tests/test_session_store.py`

