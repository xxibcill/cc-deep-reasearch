# Task 05: Operator Signals And Decision Support

## Objective

Add route-specific decision support to `/content-gen/chat` so the page helps operators spot gaps and make stronger backlog choices.

## Problem

The current chat route waits for the operator to ask everything manually. It does not expose obvious signals already derivable from the loaded backlog, such as missing categories, stale selected items, or weak evidence coverage.

## In Scope

- add lightweight insights derived from current backlog data
- expose route-level health and risk signals
- improve system feedback after apply

## Out Of Scope

- new backend scoring services
- full analytics dashboards
- changes to unrelated content-gen routes

## Candidate Signals

Surface concise indicators such as:

- selected item present or missing
- duplicate or near-duplicate idea themes
- items missing strong evidence fields
- backlog concentrated in one category or status
- stale items that have not been updated recently

These should support action, not create noise.

## Apply Feedback

After apply, show a concise audit summary:

- how many operations succeeded
- how many failed
- which ideas changed
- whether backlog reload succeeded

## Interaction Expectations

- signals should live in a side rail or summary cluster, not interrupt the transcript
- each signal can suggest a follow-up prompt or action when useful
- warnings should be compact and operational

## Likely Files

- `dashboard/src/app/content-gen/chat/page.tsx`
- `dashboard/src/components/content-gen/backlog-chat-panel.tsx`
- optional route-specific insight components

## Acceptance Criteria

- the page provides useful context before the first prompt
- signals are specific enough to drive next actions
- apply outcomes are easier to audit after changes land
- the route still feels focused rather than dashboard-bloated
