# AI Coding Tasks From Improvement Plan

This directory decomposes [IMPROVEMENT_PLAN.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/IMPROVEMENT_PLAN.md) into small, implementation-sized tasks that can be worked independently by AI coding agents.

## Task Format

Each task file contains:

- objective
- scope
- target files
- dependencies
- acceptance criteria
- exit criteria
- suggested verification

## Current Status

The original task pack remains completed, and new follow-up tasks are planned:

- Completed task records: `001` through `028`
- Planned follow-up: `029_html_first_pdf_pipeline.md`
- Planned observability follow-up sequence: `030` through `035`
- Planned LLM-routing follow-up sequence: `036` through `044`
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
- `031` should land after `030` so detailed instrumentation can reuse the stabilized event contract.
- `032` should land after `030`; it can proceed in parallel with `031`, but should land before `033` and `034` so live Claude subprocess data exists for the browser monitor.
- `033` should land after `030` and `032` so the live session store understands the final event shape and subprocess stream events.
- `034` should land after `033` and should preferably land after `031` so the UI can expose real phase, agent, and tool detail rather than placeholders.
- `035` should land after `031` through `034` because it is the integration, verification, and documentation lock-in task for the observability pack.
- `036` should land before every other LLM-routing task because it defines the shared config and route models.
- `037` should land after `036` and before `041` through `043` because planner-selected routing depends on late-bound session state.
- `038`, `039`, and `040` should land after `036`; they can proceed in parallel because they implement separate transport adapters behind the same contract.
- `041` should land after `036` and `037` so the planner emits routes against the real registry-backed contract.
- `042` should land after `037` through `041` because the analyzer path is the first active route consumer.
- `043` should land after `037` and preferably after `038` through `042` so telemetry reflects the final route and transport behavior.
- `044` should land after `042` and `043` because secondary-agent adoption and docs should describe the real mixed-session implementation rather than the planned contract.

## Definition Of Done For This Task Pack

A task is ready for implementation when:

- it has a single primary outcome
- it points to likely code locations
- it has explicit acceptance criteria
- it can be completed in one focused PR
