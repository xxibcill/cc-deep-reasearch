# Task 38: Add Golden Fixtures for Content-Gen Stages

**Status: Done**

## Goal

Create stable test fixtures for the most failure-prone content generation stages.

## Scope

- capture representative raw outputs for backlog, angle, research-pack, scripting, packaging, and QC
- test parser success against realistic happy-path outputs
- test parser degradation against malformed or sparse outputs

## Primary Files

- `tests/fixtures/`
- `tests/test_content_gen.py`

## Acceptance Criteria

- fixture-backed tests exist for the key content-gen stages
- malformed outputs are handled intentionally

## Validation

- `uv run pytest tests/test_content_gen.py -v`
