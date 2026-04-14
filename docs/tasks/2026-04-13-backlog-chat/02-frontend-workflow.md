# Task 02: Frontend Workflow

## Objective

Add a backlog chat panel to the dashboard so operators can discuss backlog changes with an LLM and explicitly apply the final proposal.

## Where To Put It

Start from:

- `dashboard/src/app/content-gen/backlog/page.tsx`
- `dashboard/src/components/content-gen/backlog-panel.tsx`

Recommended shape:

- keep the existing backlog panel
- add a new `BacklogChatPanel`
- render both in the same page as a two-panel workspace on desktop and a stacked flow on smaller screens

Suggested new component:

- `dashboard/src/components/content-gen/backlog-chat-panel.tsx`

## UX Requirements

The assistant should feel like a backlog editor, not a generic support bot.

Minimum UI:

- transcript area
- multiline composer
- send button
- loading state while waiting for assistant reply
- proposal review card
- `Apply changes` button
- inline warnings/errors

Recommended interaction flow:

1. User types a backlog question or instruction.
2. Frontend sends transcript + current backlog items to `/backlog-chat/respond`.
3. Assistant reply is appended to transcript.
4. If `operations.length > 0`, show a review card summarizing proposed creates/updates.
5. Only when the user clicks `Apply changes`, call `/backlog-chat/apply`.
6. Reload backlog after success.

## State Management

Do not put transcript state into the main global content-gen store unless it proves necessary.

Recommended v1 split:

- keep backlog CRUD state in `useContentGen`
- keep chat transcript, pending proposal, and submit/apply loading states local to `BacklogPage` or `BacklogChatPanel`
- add thin API helpers in `dashboard/src/lib/content-gen-api.ts`

This keeps the new feature isolated and easier to revert or refactor.

## Visual Direction

Match the repo’s current dashboard tone:

- dark-mode-first
- observability-style density
- restrained motion
- technical and reliable, not playful

Avoid:

- giant empty bubbles
- consumer-chat styling
- flashy gradients or novelty AI visuals

Good direction:

- compact transcript rows
- clear role distinction
- proposal card that looks like a reviewable patch, not a marketing widget
- small badges for `create`, `update`, `select`, `archive`

## Data Types

Add frontend types for:

- chat message
- chat proposal operation
- respond request/response
- apply request/response

Likely home:

- `dashboard/src/types/content-gen.ts`

## API Hooks

Add helpers in:

- `dashboard/src/lib/content-gen-api.ts`

Keep `useContentGen` focused on persisted content-gen resources. It is fine if chat uses direct API helpers from the page/component instead of expanding the store.

## Empty State

If backlog is empty, the page should still allow the chat feature to create the first item.

That means the current empty-state-only page needs to change. Replace the current hard stop with a workspace that still renders the chat panel and a lighter backlog empty state beside it.

## Apply Review Requirements

Before apply, show enough information for the operator to judge the proposal:

- operation type
- target item if any
- changed fields
- assistant reason

Do not hide the proposed mutations behind a modal.

## Acceptance Criteria

- The backlog page works with both non-empty and empty backlogs.
- A user can have a short conversation, receive a proposal, and apply it without leaving the page.
- After apply, the backlog panel refreshes and reflects the persisted changes.
- Errors from the backend are shown inline without losing the transcript.

## Advice For The Smaller Coding Agent

- Keep the first layout simple and solid. Do not spend time inventing a separate route for chat.
- Use the existing UI primitives unless you have a real gap.
- Avoid over-centralizing state. This feature is page-local.
- Preserve responsiveness. Desktop can be split-view; mobile should stack chat first, backlog second.
