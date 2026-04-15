# Task P4-T3: Pipeline And Stage Surface Integration

## Objective

Integrate managed brief identity and lifecycle state back into pipeline observability and control surfaces.

## Scope

- Link pipeline detail pages to the managed brief resource when present.
- Show brief revision and approval metadata in the stage panel and pipeline header where useful.
- Add actions such as “open brief” or “start from approved brief” from relevant screens.
- Keep old inline-only pipeline views readable during migration.

## Acceptance Criteria

- Operators can move naturally between a pipeline run and its managed brief.
- Stage output views show whether the brief is a snapshot, a live managed resource, or an outdated revision.
- Existing observability value is preserved instead of being replaced by opaque links.

## Advice For The Smaller Coding Agent

- Preserve direct stage visibility. Operators should not lose easy access to the content that the stage produced.
- Distinguish snapshot versus current-head data clearly in the UI.
