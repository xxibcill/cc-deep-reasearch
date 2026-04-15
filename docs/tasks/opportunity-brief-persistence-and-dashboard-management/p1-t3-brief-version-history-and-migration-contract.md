# Task P1-T3: Brief Version History And Migration Contract

## Objective

Define how existing generated briefs move from inline pipeline state into the new persistent brief system without losing provenance.

## Scope

- Define revision history representation and metadata.
- Specify how to import or hydrate legacy briefs from saved `PipelineContext` payloads.
- Decide when a legacy brief gets a new managed resource id versus only a synthetic revision.
- Document fallback behavior when migration metadata is incomplete.

## Acceptance Criteria

- Existing saved pipeline runs can be interpreted under the new brief-management model.
- Operators can still distinguish original generated content from later edits after migration.
- Migration rules are explicit enough to implement incrementally without data loss.

## Advice For The Smaller Coding Agent

- Bias toward append-only migration behavior. Preserve old payloads rather than trying to rewrite them aggressively.
- Make incomplete provenance visible instead of fabricating certainty.
