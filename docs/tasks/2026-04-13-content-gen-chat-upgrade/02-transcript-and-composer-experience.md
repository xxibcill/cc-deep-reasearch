# Task 02: Transcript And Composer Experience

## Objective

Upgrade the core conversation experience on `/content-gen/chat` so operators can read, continue, and steer backlog discussions efficiently.

## Problem

The current transcript is functional but minimal:

- assistant output is rendered as plain text
- message rows are visually shallow
- there are no quick-start prompts
- composer behavior is basic and does not guide the user

This makes the route feel like a raw debug panel instead of an operator tool.

## In Scope

- improve transcript presentation
- improve composer ergonomics
- add fast-start prompt actions
- refine loading and disabled states

## Out Of Scope

- proposal diff expansion
- local persistence
- additional backend intelligence

## Required Improvements

### Transcript

- render assistant content as markdown
- improve distinction between user and assistant entries
- add compact metadata such as role labels and timestamps if useful
- keep the transcript dense and technical, not consumer-chat styled

### Composer

- support better autosizing behavior
- make submit affordances clearer
- preserve `Enter` to send and `Shift+Enter` for newline
- show meaningful disabled states during load/apply

### Prompt Starters

Add a few route-specific starter actions, for example:

- identify weak backlog items
- create missing idea variants
- suggest higher-priority reframes
- strengthen evidence or proof angles

These should seed the composer or send a message directly.

## Suggested Files

- `dashboard/src/components/content-gen/backlog-chat-panel.tsx`
- any route-specific child components extracted from it

## Acceptance Criteria

- transcript is easier to scan during longer conversations
- assistant output supports structured formatting
- operators can start common tasks without typing from scratch
- the composer feels responsive and deliberate, not improvised

## Design Direction

- maintain the existing dark, observability-style language
- avoid giant bubbles or novelty assistant visuals
- keep rows compact and purposeful
