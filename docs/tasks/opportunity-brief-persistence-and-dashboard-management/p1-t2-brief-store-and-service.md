# Task P1-T2: Brief Store And Service

## Objective

Add a first-class persistence and service layer for `OpportunityBrief` resources that matches the quality bar of backlog management.

## Scope

- Add a brief store abstraction with path/config resolution.
- Support list, load, create, save revision, update head, and archive operations.
- Add a service layer that owns validation, timestamps, and lifecycle transitions.
- Keep storage implementation details behind a narrow interface so YAML and SQLite strategies remain swappable.

## Acceptance Criteria

- Briefs can be persisted and reloaded independently of pipeline runs.
- Service methods centralize lifecycle rules instead of scattering write logic across routes.
- The design leaves room for a future SQLite-backed implementation without rewriting every caller.

## Advice For The Smaller Coding Agent

- Reuse backlog service patterns where they truly fit, especially around normalization and explicit mutation APIs.
- Do not let routes or UI code write raw brief payloads directly.
