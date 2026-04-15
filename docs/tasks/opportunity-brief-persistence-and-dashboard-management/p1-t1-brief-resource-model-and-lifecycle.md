# Task P1-T1: Brief Resource Model And Lifecycle

## Objective

Define the canonical persisted `OpportunityBrief` resource, including lifecycle states, provenance fields, and mutable versus immutable boundaries.

## Scope

- Separate resource identity from revision identity.
- Define statuses such as draft, approved, archived, and superseded.
- Clarify which fields are operator-editable, system-managed, or historical.
- Define provenance for generated, imported, cloned, and operator-created briefs.

## Acceptance Criteria

- The system has a documented managed brief model that is stable enough for storage and API work.
- It is clear how a generated brief differs from an edited revision and an approved revision.
- The lifecycle supports auditability without requiring overwrite-in-place semantics.

## Advice For The Smaller Coding Agent

- Prefer immutable revisions plus a current-head pointer over destructive edits.
- Keep the first lifecycle small and explicit. Add only the states the product will actually use.
