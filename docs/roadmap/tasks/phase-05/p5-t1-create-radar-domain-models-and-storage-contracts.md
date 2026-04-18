# P5-T1 - Create Radar Domain Models And Storage Contracts

## Status

Proposed.

## Summary

Create the backend package and typed domain models for Radar so later tasks can build on stable contracts instead of guessing field shapes.

## Why This Task Exists

Small agents fail when they start from routes or UI without a clear data model. This task creates the canonical Radar schema first.

## Scope

- Create a new backend package such as `src/cc_deep_research/radar/`.
- Add domain models for `RadarSource`, `RawSignal`, `Opportunity`, `OpportunityScore`, `OpportunityFeedback`, and `OpportunityWorkflowLink`.
- Add enums or literals for source type, opportunity type, status, priority label, and feedback type.
- Decide and document how Radar data is persisted on disk.

## Out Of Scope

- No FastAPI routes yet.
- No scanning logic yet.
- No dashboard code yet.

## Read These Files First

- `src/cc_deep_research/content_gen/storage/backlog_store.py`
- `src/cc_deep_research/content_gen/storage/derivative_opportunity_store.py`
- `src/cc_deep_research/content_gen/storage/_paths.py`
- `src/cc_deep_research/research_runs/models.py`
- `src/cc_deep_research/content_gen/models.py`

## Suggested Files To Create Or Change

- `src/cc_deep_research/radar/__init__.py`
- `src/cc_deep_research/radar/models.py`
- `src/cc_deep_research/radar/storage.py` or `src/cc_deep_research/radar/stores.py`
- `src/cc_deep_research/config/schema.py` only if a new config path is required
- `tests/test_radar_models.py`

## Implementation Guide

1. Create the `radar` package under `src/cc_deep_research/`.
2. Define the domain models first. Do not start with persistence code.
3. Prefer Pydantic models because the rest of the codebase already uses them for validation and serialization.
4. Include enough metadata for auditability:
   - ids
   - created and updated timestamps
   - first and latest detection times
   - provenance fields linking opportunities back to signals
5. Reuse existing content-gen storage patterns for path resolution instead of inventing a separate storage convention.
6. Pick one simple V1 persistence shape. Recommended approach:
   - YAML or JSON files for Radar entities if that matches existing local storage usage
   - avoid adding a database migration unless you find an existing store that clearly expects one
7. Add model tests for:
   - valid construction
   - enum serialization
   - default values
   - status and priority validation

## Guardrails For A Small Agent

- Do not put business logic into the models beyond validation and normalization.
- Do not add route handlers here.
- Do not create half of the models and leave the rest for later; this task is the canonical schema task.

## Deliverables

- New Radar backend package
- Typed Radar models
- Initial persistence contract and file path strategy
- Model-level tests

## Dependencies

- Opportunity Radar PRD

## Verification

- Run `uv run pytest tests/test_radar_models.py -v`
- Import the new models from a Python shell or test without circular import failures

## Acceptance Criteria

- The Radar domain shape is explicit enough for later backend and frontend tasks to rely on.
- Models cover sources, signals, opportunities, scores, feedback, and workflow links.
- Persistence location and serialization format are documented in code.
