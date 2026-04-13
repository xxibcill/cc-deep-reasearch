# Task 03: Proposal Review Diff Workflow

## Objective

Make proposed backlog mutations reviewable enough that operators can apply them with confidence from `/content-gen/chat`.

## Problem

The current proposal card only shows:

- operation type
- short reason
- target id for updates
- changed field names

That is not enough context for real editing decisions.

## In Scope

- enrich proposal rendering before apply
- show field-level before/after information when possible
- support better filtering or removal of unwanted operations before apply
- highlight high-risk mutations

## Out Of Scope

- backend schema redesign
- autonomous apply
- new mutation types beyond the existing contract unless absolutely required

## Required Review UX

For each pending operation, show:

- operation kind
- target item context
- assistant reason
- changed fields
- current value and proposed value when an existing item is being updated

For creates, show:

- the proposed new record fields in a readable summary

For risky edits, highlight:

- selected item changes
- status changes
- large content rewrites
- operations with sparse supporting rationale

## Recommended Interaction Model

- group operations by target item when helpful
- allow dismissing one operation without clearing the whole proposal
- keep the final `Apply changes` action explicit
- keep apply errors attached to the relevant review surface

## Likely Files

- `dashboard/src/components/content-gen/backlog-chat-panel.tsx`
- optional extracted proposal components
- shared backlog formatting helpers if useful

## Acceptance Criteria

- operators can understand what will change before apply
- updates are reviewable without opening another page
- proposal dismissal can happen at operation level or full-proposal level
- partial apply failures remain understandable in the UI

## Implementation Note

Do not hide the review state behind a modal. The route should behave like a visible patch-review surface.
