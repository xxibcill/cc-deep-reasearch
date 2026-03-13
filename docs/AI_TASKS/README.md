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

All tasks in the AI Task Pack have been completed:

- Completed task records: `001` through `028`
- Report readability follow-up sequence: `018` through `023` ✓
- Report writing cleanup follow-up sequence: `024` through `028` ✓

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
- `018` should land before `019`, `021`, and `022` because those tasks need section-aware PDF hooks.
- `019` should land before `022` so appendix styling builds on the new typographic baseline.
- `020` can land independently of the PDF hook work, but should land before `023` so tests reflect the final executive-summary shape.
- `021` should land after `018` and before `022` so the source appendix structure exists before it is de-emphasized.
- `022` should land after `019` and `021`.
- `023` should land after `018` through `022` and should lock the readability changes in place.
- `024` should land before `025` and `027` so Executive Summary behavior has a single implementation surface.
- `025` should land after `024` and before `027` and `028` so the final summary wording contract is in place.
- `026` should land after `024`; it can proceed independently of `025`, but should land before `028` so the fixture refresh reflects the real report pipeline.
- `027` should land after `024` and `025` so the guardrails reflect the finalized summary contract.
- `028` should land after `025`, `026`, and `027` because it is a fixture-refresh and verification task.

## Definition Of Done For This Task Pack

A task is ready for implementation when:

- it has a single primary outcome
- it points to likely code locations
- it has explicit acceptance criteria
- it can be completed in one focused PR
