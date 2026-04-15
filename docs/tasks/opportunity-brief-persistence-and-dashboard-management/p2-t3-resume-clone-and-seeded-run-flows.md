# Task P2-T3: Resume, Clone, And Seeded Run Flows

## Objective

Support execution flows that start from or branch from a managed brief rather than always re-running opportunity planning from scratch.

## Scope

- Add start-from-brief and clone-from-brief semantics for dashboard-triggered runs.
- Define how resume behavior works when the source brief has changed since the original run.
- Preserve provenance when an operator branches a new run from an older approved brief revision.
- Keep seeded runs explainable in the pipeline detail view.

## Acceptance Criteria

- Operators can start a new run from a chosen brief version deliberately.
- Resume behavior does not silently jump to a newer brief revision.
- Branching and cloning preserve enough provenance for later debugging and trust.

## Advice For The Smaller Coding Agent

- Use explicit revision pinning. Rebinding old runs to the latest brief head will be confusing and unsafe.
- Keep the first seeded-run entry points narrow and operator-driven.
