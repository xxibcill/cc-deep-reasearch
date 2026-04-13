# Task 01: Backend Contract

**Status: Done**

## Objective

Add a server-side backlog chat workflow that:

- receives transcript + backlog context
- calls an LLM-backed assistant
- returns a conversational reply plus structured backlog operations
- applies approved operations through `BacklogService`

## Scope

Create two new endpoints under the existing content-gen API namespace:

- `POST /api/content-gen/backlog-chat/respond`
- `POST /api/content-gen/backlog-chat/apply`

Recommended new modules:

- `src/cc_deep_research/content_gen/agents/backlog_chat.py`
- `src/cc_deep_research/content_gen/prompts/backlog_chat.py`

You may also add supporting models either in `models.py` or locally in `router.py` if you want to keep the initial scope smaller.

## Request / Response Contract

### `POST /respond`

Request shape:

```json
{
  "messages": [
    { "role": "user", "content": "Help me turn this backlog into a sharper evergreen slate." }
  ],
  "backlog_items": [],
  "strategy": null,
  "selected_idea_id": null
}
```

Response shape:

```json
{
  "reply_markdown": "Here is what I would tighten first...",
  "apply_ready": true,
  "warnings": [],
  "operations": [
    {
      "kind": "update_item",
      "idea_id": "abc12345",
      "reason": "The current framing is too broad for an authority-building slot.",
      "fields": {
        "idea": "A narrower replacement idea",
        "category": "authority-building"
      }
    },
    {
      "kind": "create_item",
      "reason": "This fills the missing beginner-proof lane.",
      "fields": {
        "idea": "New idea",
        "audience": "Beginner founders",
        "problem": "They keep copying advanced tactics too early."
      }
    }
  ],
  "mentioned_idea_ids": ["abc12345"]
}
```

### `POST /apply`

Request shape:

```json
{
  "operations": [
    {
      "kind": "update_item",
      "idea_id": "abc12345",
      "reason": "Narrow the scope",
      "fields": {
        "idea": "Replacement idea"
      }
    }
  ]
}
```

Response shape:

```json
{
  "applied": 1,
  "items": [],
  "errors": []
}
```

## Recommended Data Rules

- `respond` is advisory only. It must never write.
- `apply` is the only write path.
- `apply` should reject unknown operation kinds.
- `apply` should reject `update_item` without `idea_id`.
- `apply` should reject empty `create_item.fields.idea`.
- `apply` should reject fields outside the supported backlog schema.
- `apply` should continue returning structured errors instead of crashing the route.

## LLM Contract

Create a dedicated backlog-chat agent instead of overloading the current backlog builder/scorer agent.

Recommended agent behavior:

- Read the current backlog snapshot and recent conversation.
- Give concise editorial advice.
- Propose only operations that are justified by the conversation.
- Prefer updating existing items over creating duplicates.
- Avoid destructive actions.
- Return JSON-only output from the prompt.

Suggested output model:

- `reply_markdown: str`
- `apply_ready: bool`
- `warnings: list[str]`
- `operations: list[BacklogChatOperation]`
- `mentioned_idea_ids: list[str]`

## Parsing Guidance

- Expect the model to occasionally wrap JSON in code fences.
- Add a small JSON extractor instead of assuming perfect output.
- If parsing fails, return:
  - a safe fallback `reply_markdown`
  - `apply_ready=false`
  - `operations=[]`
  - a warning explaining that no structured proposal was produced

Do not let malformed model output reach the apply route.

## BacklogService Integration

Use the existing methods where possible:

- `create_item(...)`
- `update_item(...)`
- `select_item(...)`
- `archive_item(...)`

If needed, add one helper method to apply a validated list of operations in order. Keep it narrow and deterministic.

## Acceptance Criteria

- Chat responses are generated server-side through the repo’s LLM routing path.
- Applying a proposal updates `backlog.yaml` through service methods, not direct file writes.
- Invalid operations return structured errors and do not partially corrupt backlog state.
- The route contract is stable enough for the dashboard to consume without guessing.

## Advice For The Smaller Coding Agent

- Do not add session persistence in this task. It is not required for the v1 loop.
- Keep new models close to the router if that helps you ship faster, but avoid anonymous dict soup in the route body.
- Make the apply path boring and heavily validated.
- If you need to choose between richer assistant prose and safer structured ops, pick safer structured ops.
