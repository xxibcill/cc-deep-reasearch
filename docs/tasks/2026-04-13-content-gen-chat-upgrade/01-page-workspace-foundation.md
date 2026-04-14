# Task 01: Page Workspace Foundation

## Objective

Turn `/content-gen/chat` into a real workspace page instead of a thin wrapper around `BacklogChatPanel`.

## Problem

Current `dashboard/src/app/content-gen/chat/page.tsx` only mounts the shared chat panel inside a fixed-height container. The route has almost no page-level hierarchy, no contextual framing, and no structure for richer route-specific features.

## In Scope

- replace the fixed-height shell in `dashboard/src/app/content-gen/chat/page.tsx`
- introduce a route-specific workspace layout for desktop and mobile
- add page-level summary elements for backlog context
- reserve clear regions for transcript, context, and proposal review

## Out Of Scope

- field-level proposal diffs
- transcript persistence
- new backend endpoints
- redesigning `/content-gen/backlog`

## Recommended Shape

Build a dedicated route-level layout with three functional regions:

1. main chat thread area
2. backlog context rail
3. review/apply rail

Responsive behavior:

- desktop: multi-column workspace
- tablet: two-column collapse is acceptable
- mobile: stacked flow with chat first

## UX Requirements

- remove `h-[calc(100vh-12rem)]`
- preserve use inside the existing content-gen shell
- show route title and one-line framing
- show current backlog count and selected idea status at page level
- keep the layout usable even when backlog is empty

## Likely File Shape

- keep `dashboard/src/app/content-gen/chat/page.tsx` as the route entry
- optionally extract a route-specific container such as `dashboard/src/components/content-gen/chat-workspace.tsx`
- keep reusable rendering logic in `backlog-chat-panel.tsx` only if that does not make the component harder to reason about

## Acceptance Criteria

- `/content-gen/chat` no longer looks like a single embedded widget
- the page has an intentional information hierarchy
- the route remains responsive and usable on small screens
- empty backlog state still supports starting a conversation

## Notes

If you need to split `BacklogChatPanel` into smaller pieces, prefer clear ownership:

- route layout and workspace composition in a route-specific component
- transcript/composer logic in a chat-focused component
- proposal rendering in a proposal-focused component
