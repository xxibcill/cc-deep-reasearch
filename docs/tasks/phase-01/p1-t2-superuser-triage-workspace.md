# Task P1-T2: Superuser Triage Workspace

## Objective

Create a backlog workspace that lets a superuser run AI triage, review the resulting proposal set, and apply approved changes in bulk.

## Scope

- Add an AI triage entrypoint to the main backlog page.
- Show proposal groups such as duplicates, weak items, missing evidence, and recommended reframes.
- Support selective apply, not just apply-all.
- Preserve the current backlog browsing and detail navigation behavior.

## UX Requirements

- The workspace should feel like an operator console, not a chat toy.
- The proposal list should clearly show:
  - operation type
  - affected items
  - changed fields
  - AI rationale
  - apply status
- The superuser must be able to:
  - run triage
  - inspect recommendations
  - accept or reject individual proposals
  - apply approved proposals

## Acceptance Criteria

- A superuser can run AI triage from the backlog page without leaving backlog management.
- The UI supports partial approval of a batch proposal set.
- Applied results refresh the backlog state and surface any failed operations inline.

## Advice For The Smaller Coding Agent

- Keep workspace state local unless shared persistence becomes necessary.
- Favor dense, review-oriented layouts over chat-first layouts.
- Make rejected and applied proposal states easy to audit visually.
