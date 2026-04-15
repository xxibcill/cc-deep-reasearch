# Task P5-T1: Brief Assistant Workspace

## Objective

Add an AI-assisted workspace for discussing and proposing brief refinements without directly mutating persisted state.

## Scope

- Add conversational and structured proposal flows for brief edits.
- Return suggested operations, field changes, or alternate brief drafts.
- Add explicit apply routes that turn accepted proposals into revisions.
- Preserve enough context for the operator to understand what the assistant is changing and why.

## Acceptance Criteria

- Operators can use AI to refine a brief without losing manual control over persistence.
- Proposed changes are reviewable before they become a saved revision.
- The system preserves a clear boundary between assistant conversation state and managed brief state.

## Advice For The Smaller Coding Agent

- Keep the first assistant flow bounded to concrete brief fields and revision notes.
- Avoid free-form prompt dumping as the only explanation of what changed.
