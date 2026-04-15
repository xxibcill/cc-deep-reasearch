# Task P2-T1: Pipeline Context Reference Model

## Objective

Teach pipeline state and saved jobs to reference a managed brief resource and revision while remaining backward-compatible with inline brief payloads.

## Scope

- Add managed brief identifiers and revision references to `PipelineContext` or adjacent run metadata.
- Define when the pipeline still embeds a brief snapshot for portability and inspection.
- Ensure browser-started job persistence and resume flows preserve the reference cleanly.
- Clarify how old saved jobs without references are interpreted.

## Acceptance Criteria

- A pipeline run can identify exactly which brief resource and revision it used.
- Saved jobs remain inspectable even if the linked managed brief changes later.
- Inline-only historical runs still load correctly during the transition period.

## Advice For The Smaller Coding Agent

- Keep the reference model explicit and boring. Hidden inference between run state and brief state will create recovery bugs later.
- Preserve a readable snapshot for observability even when the managed reference is the source of truth.
