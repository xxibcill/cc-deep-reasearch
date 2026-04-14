# Backlog Chat Assistant Task Pack

## Goal

Add a new operator-facing feature on the content-generation backlog page: a chat interface that lets a user discuss backlog ideas with an LLM, then explicitly apply the final create/edit decisions back into the persistent backlog.

This should extend the current backlog workflow instead of creating a parallel system.

## Why This Fits The Existing Repo

- The dashboard already has a dedicated backlog page at `dashboard/src/app/content-gen/backlog/page.tsx`.
- Backlog persistence already exists through `BacklogService` and `BacklogStore`.
- The content-generation subsystem already has LLM-backed agents and prompt contracts.
- The FastAPI router already exposes CRUD endpoints for the backlog.

The missing piece is a guided assistant workflow between "read backlog" and "manually edit one row."

## Product Shape For V1

The assistant should feel like an editor embedded in the backlog workspace, not a generic chatbot.

Core behavior:

1. The operator opens the backlog page and sees the current items.
2. The operator chats with the assistant about gaps, priorities, reframes, new ideas, or edits.
3. The backend sends the transcript plus a compact backlog snapshot to an LLM-backed agent.
4. The assistant replies in normal language and may include a structured proposal for backlog mutations.
5. Nothing is written automatically.
6. The operator explicitly clicks `Apply changes`.
7. The backend validates and applies the proposal through `BacklogService`.
8. The page refreshes the backlog and shows what changed.

## Hard V1 Constraints

- No autonomous writes during chat turns.
- No assistant-driven delete operation.
- No hidden prompt execution in the browser. All LLM calls stay server-side.
- No new persistence model for backlog data. Writes must go through `BacklogService`.
- No long-lived backend chat session store for v1. Keep the chat request stateless: the client sends transcript + current backlog snapshot each turn.

## Recommended User Experience

- Place the chat panel on the backlog page, above or beside the existing backlog panel.
- Frame it as backlog coaching and mutation planning, not open-ended Q&A.
- Keep the assistant response split into two layers:
  - conversational guidance in markdown
  - a machine-readable proposal for optional apply
- Show proposal operations in a compact review card before apply.
- Require a deliberate operator action for apply.

## Proposed Operation Types

Keep the assistant narrow and useful. V1 should support:

- `create_item`
- `update_item`
- `select_item`
- `archive_item`

Do not support:

- `delete_item`
- bulk free-form YAML replacement
- direct file edits from the frontend

## Suggested Implementation Order

1. Backend contract and LLM adapter
2. Apply path wired into `BacklogService`
3. Frontend chat panel and proposal review
4. End-to-end verification

## Files That Matter

- `dashboard/src/app/content-gen/backlog/page.tsx`
- `dashboard/src/components/content-gen/backlog-panel.tsx`
- `dashboard/src/lib/content-gen-api.ts`
- `dashboard/src/hooks/useContentGen.ts`
- `dashboard/src/types/content-gen.ts`
- `src/cc_deep_research/content_gen/router.py`
- `src/cc_deep_research/content_gen/backlog_service.py`
- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/agents/_llm_utils.py`
- `src/cc_deep_research/llm/router.py`

## Task Files

- `01-backend-contract.md`
- `02-frontend-workflow.md`
- `03-tests-and-ship-checklist.md`

## Advice For The Smaller Coding Agent

- Keep v1 tight. The main risk is overbuilding session infrastructure before the chat-to-apply loop works.
- Reuse existing content-gen patterns for prompt construction and router-backed LLM calls.
- Treat malformed assistant JSON as expected input, not an edge case.
- Bias toward explicit validation and fail-closed apply behavior.
- If a change is not safe to apply automatically, return it as discussion text only and leave `operations` empty.
