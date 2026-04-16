# P1-T1 - Define Compressed Operating Contract

## Objective

Publish the seven-phase operating model as the canonical workflow view and map the existing 14-stage implementation into it.

## Scope

- define the seven operating phases and the stage-to-phase mapping
- document which current artifacts remain and which become grouped phase outputs
- describe compatibility rules for CLI, dashboard, and saved `PipelineContext` runs

## Affected Areas

- `docs/content-generation.md`
- `docs/content-gen-workflow-template.md`
- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/orchestrator.py`

## Dependencies

- the current `PIPELINE_STAGES` order and stage contract registry

## Acceptance Criteria

- every current stage maps to one of the seven operating phases
- docs and typed metadata use the same phase names
- migration notes explain how grouped phases relate to existing artifacts
