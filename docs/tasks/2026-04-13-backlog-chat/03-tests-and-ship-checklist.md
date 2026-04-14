# Task 03: Tests And Ship Checklist

## Objective

Verify that the backlog chat feature is safe, deterministic enough for v1, and wired through the existing dashboard and content-gen backend without regressions.

## Backend Tests

Add pytest coverage for:

- `respond` route returning a parsed proposal from mocked LLM output
- `respond` route falling back safely on malformed model output
- `apply` route creating a new backlog item
- `apply` route updating an existing backlog item
- `apply` route rejecting invalid operation kinds
- `apply` route rejecting missing `idea_id` for update/select/archive

Good candidate locations:

- `tests/test_content_gen.py`
- a new focused test file such as `tests/test_content_gen_backlog_chat.py`

## Frontend Verification

There is no obvious unit-test harness for React components in the dashboard package, so prefer Playwright coverage for the user flow.

Add or extend an e2e spec around the backlog page:

- open backlog page
- send a chat prompt
- receive a mocked assistant proposal
- apply the proposal
- verify the backlog UI refreshes with the new/updated item

Likely file:

- `dashboard/tests/e2e/backlog-management.spec.ts`

## Manual Verification Checklist

- backlog page still loads when `backlog.yaml` is empty
- chat works with a populated backlog
- apply does not fire automatically after assistant response
- update operations preserve unrelated fields
- failed apply shows an inline error and keeps the transcript
- page refresh after apply shows persisted data from the backend, not just optimistic local state

## Suggested Dev Commands

Backend:

```bash
uv run pytest tests/test_content_gen.py tests/test_content_gen_backlog_chat.py -q
```

Frontend:

```bash
cd dashboard
npm run lint
npm run test:e2e -- --grep backlog
```

## Non-Goals For This Slice

Do not expand scope into:

- chat history persistence across browser reloads
- assistant delete support
- collaborative multi-user conflict handling
- background scoring/research jobs triggered directly from chat
- a generalized chat framework for every content-gen stage

## Ship Bar

This feature is ready for a first merge when:

- the chat-to-proposal-to-apply loop works end to end
- failed model output degrades safely
- persisted backlog edits go through the current service layer
- the dashboard experience remains readable on desktop and mobile

## Advice For The Smaller Coding Agent

- Mock the LLM path in tests early. Do not make test reliability depend on live providers.
- Keep the feature behind the current backlog page rather than introducing navigation churn.
- If time gets tight, cut polish before cutting validation.
