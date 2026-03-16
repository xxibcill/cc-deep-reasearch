# Task 001: Introduce Shared Research Run Contract

Status: Planned

## Objective

Define a typed, framework-agnostic contract for starting a research run and returning its results.

## Scope

- add input models for the options currently parsed by the CLI
- add output models for session identity, persisted artifacts, and final report metadata
- keep the models free of `click` and `fastapi` imports

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/research_runs/models.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/research_runs/__init__.py`

## Dependencies

- none

## Acceptance Criteria

- there is one shared request model for research execution inputs
- there is one shared result model for completed research outputs
- CLI- and API-specific naming differences are handled at the adapter layer, not in the models

## Suggested Verification

- run `uv run pytest tests/test_models.py`

