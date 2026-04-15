# Task P3-T1: Brief Management API

## Objective

Expose the backend routes needed to list, inspect, create, edit, approve, archive, and version persistent briefs.

## Scope

- Add list and detail routes for briefs and their revisions.
- Add create, edit, approve, archive, and clone endpoints.
- Return resource metadata needed by dashboard filtering and status displays.
- Keep route contracts aligned with the service layer rather than leaking storage details.

## Acceptance Criteria

- The dashboard can manage briefs through a first-class API surface instead of piggybacking on pipeline detail payloads.
- Operators can request current-head and historical revision data explicitly.
- API responses carry enough status and provenance metadata for UI decisions without extra prompt parsing.

## Advice For The Smaller Coding Agent

- Keep CRUD semantics explicit and predictable. A “save whatever blob came from the client” route is not sufficient here.
- Prefer narrow request models over loosely typed patch dictionaries for state-changing operations that alter lifecycle state.
