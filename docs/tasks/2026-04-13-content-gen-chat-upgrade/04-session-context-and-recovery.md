# Task 04: Session Context And Recovery

## Objective

Preserve enough local chat state on `/content-gen/chat` that operators can refresh, navigate briefly, or resume work without losing context.

## Problem

Today the route stores transcript, draft input, and pending proposal entirely in volatile component state. A refresh or remount loses the conversation and forces the operator to restart.

## In Scope

- persist transcript locally in the browser
- persist draft input and pending proposal state
- restore route state safely on revisit or refresh
- improve visible context signals around selected and mentioned ideas

## Out Of Scope

- backend chat session storage
- cross-device sync
- long-lived collaborative sessions

## Required Behaviors

- restore the latest local session for `/content-gen/chat`
- recover unsent draft input
- recover pending proposal state if it has not been applied
- allow the operator to clear or reset the local session intentionally

## Context Signals

Add lightweight context affordances such as:

- selected idea chip
- recently mentioned idea chips
- pinned backlog items used as discussion anchors

These should help the operator understand what the assistant is using as context without introducing a heavy state model.

## Safety Notes

- local recovery must not auto-apply anything
- stale restored proposal state should be clearly marked if the backlog has changed
- if exact validation is too expensive for v1, at minimum show a warning and require manual re-apply review

## Likely Files

- `dashboard/src/components/content-gen/backlog-chat-panel.tsx`
- route-specific helpers under `dashboard/src/lib` if needed
- `dashboard/src/types/content-gen.ts` only if local UI types need to be formalized

## Acceptance Criteria

- refresh does not wipe active work by default
- operators can tell which ideas are in current context
- recovered state is clearly recoverable and clearly resettable
- no writes happen automatically during restore
