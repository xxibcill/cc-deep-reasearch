# Task P6-T2: Observability, Tests, And Failure Recovery

## Objective

Add the test coverage and observability needed to trust the new brief system under normal use and partial-failure conditions.

## Scope

- Add unit and integration coverage for storage, service, API, and pipeline linkage behavior.
- Add dashboard or end-to-end coverage for critical operator flows.
- Add telemetry, traces, or logs for brief creation, revision, approval, and apply events.
- Define recovery behavior for edit conflicts, failed applies, and missing linked records.

## Acceptance Criteria

- The main brief-management workflows have automated coverage.
- Operators and developers can diagnose failed edits or linkage problems without inspecting raw files manually.
- Recovery behavior is defined for the most likely storage and concurrency failures.

## Advice For The Smaller Coding Agent

- Focus tests on lifecycle transitions and provenance integrity, not only happy-path rendering.
- Instrument the events operators care about, especially approval and apply outcomes.
