# AI Coding Tasks From Improvement Plan

This directory decomposes [IMPROVEMENT_PLAN.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/IMPROVEMENT_PLAN.md) into small, implementation-sized tasks that can be worked independently by AI coding agents.

## Task Format

Each task file contains:

- objective
- scope
- target files
- dependencies
- acceptance criteria
- suggested verification

## Current Status

The original task pack is implemented through the runtime-boundary follow-up.

- Completed task records: `001` through `016`
- Current follow-up task: [017_local_scaffolding_api_cleanup.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/017_local_scaffolding_api_cleanup.md)

The completed task files are kept in this directory as implementation records so contributors can trace the original intent and verification notes.

## Dependency Notes

- `001` and `002` reduce ambiguity for almost every later task.
- `003` should land before major orchestrator refactors.
- `005` should land before `006`.
- `006` and `007` should land before `010`.
- `009` should land before `012`.
- `013` should land before `014`.
- `016` should land after `003` and should be treated as the concrete follow-through for the architecture-honesty work started in `011`.
- `017` should land after `016` and should narrow the remaining compatibility API surface around the local runtime.

## Definition Of Done For This Task Pack

A task is ready for implementation when:

- it has a single primary outcome
- it points to likely code locations
- it has explicit acceptance criteria
- it can be completed in one focused PR
