# Task P3-T1: Persistence And Concurrency

## Objective

Prepare backlog storage for heavier AI-assisted usage where batch operations, concurrent sessions, or background workflows make single-file persistence increasingly fragile.

## Scope

- Evaluate and implement a stronger persistence model such as SQLite or Postgres-backed storage.
- Preserve the `BacklogService` interface as the primary application boundary where possible.
- Add safe concurrency behavior for overlapping reads and writes.
- Plan or implement a migration path from the current YAML backlog.

## Acceptance Criteria

- Backlog reads and writes remain consistent under heavier operator and AI-assisted usage.
- The service layer can enforce safe updates without relying on best-effort file writes.
- Migration risks and rollback strategy are documented if storage changes are introduced.

## Advice For The Smaller Coding Agent

- Do not rewrite the whole content-gen stack around storage changes.
- Keep compatibility shims if needed so the UI and service layer stay stable during migration.
- Treat migration and rollback planning as part of the deliverable.
