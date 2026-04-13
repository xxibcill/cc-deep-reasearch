# Content Gen Chat Page Upgrade Task Pack

## Goal

Upgrade the dedicated content generation chat route at `/content-gen/chat` from a thin panel mount into a focused operator workspace.

The route should remain scoped to backlog-chat workflows, but it should feel like a full page with stronger context, better reviewability, and safer apply behavior.

## Scope Boundary

Primary route in scope:

- `dashboard/src/app/content-gen/chat/page.tsx`

Supporting files may be touched only when needed to improve that route:

- `dashboard/src/components/content-gen/backlog-chat-panel.tsx`
- `dashboard/src/components/content-gen/backlog-shared.ts`
- `dashboard/src/lib/content-gen-api.ts`
- `dashboard/src/types/content-gen.ts`
- route-specific tests under `dashboard/tests/e2e`

Out of scope:

- redesigning `/content-gen/backlog`
- changing backlog persistence rules
- introducing autonomous writes
- building a generalized chat framework for every content-gen surface

## Why This Upgrade Matters

The current chat route only renders the existing `BacklogChatPanel` inside a fixed-height wrapper. That is enough for a minimal demo, but not enough for sustained operator use.

Current weaknesses:

- no page-level information architecture
- no visible backlog context beyond small badges
- proposal review is too shallow for confident apply
- transcript state is lost on refresh
- route-specific tests do not protect the experience

## Product Direction

Treat `/content-gen/chat` as a specialized backlog editing console:

1. conversation in the center
2. backlog context visible beside it
3. proposal review and apply controls always legible
4. safe, explicit mutation workflow
5. resilient handling for empty, slow, partial-failure, and refresh cases

## Suggested Execution Order

1. `01-page-workspace-foundation.md`
2. `02-transcript-and-composer-experience.md`
3. `03-proposal-review-diff-workflow.md`
4. `04-session-context-and-recovery.md`
5. `05-operator-signals-and-decision-support.md`
6. `06-tests-and-ship-checklist.md`

## Advice For The Smaller Coding Agent

- Keep the route specialized. Do not broaden it into a generic assistant shell.
- Bias toward extracting route-specific containers rather than overloading the shared backlog page.
- If shared components are changed, preserve the current `/content-gen/backlog` behavior unless the task explicitly says otherwise.
- Show enough proposal detail for operator trust before adding more “AI” affordances.
