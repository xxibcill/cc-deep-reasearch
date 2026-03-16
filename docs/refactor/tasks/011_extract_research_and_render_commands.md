# Task 011: Extract Research And Render Commands

Status: Done

## Objective

Move research execution and markdown conversion commands out of the central CLI module.

## Scope

- extract `research`, `markdown-to-html`, and `markdown-to-pdf` commands into dedicated modules
- keep flag names and output behavior stable
- keep orchestration calls shallow and explicit

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/cli.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/cli/research.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/cli/render.py`

## Dependencies

- [010_extract_cli_bootstrap.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/010_extract_cli_bootstrap.md)

## Acceptance Criteria

- research and render commands are isolated from unrelated admin commands
- the command modules delegate to services instead of holding extra workflow logic
- tests cover the extracted command behavior

## Suggested Verification

- run `uv run pytest tests/test_cli_monitoring.py tests/test_markdown_to_pdf.py tests/test_orchestrator.py`
