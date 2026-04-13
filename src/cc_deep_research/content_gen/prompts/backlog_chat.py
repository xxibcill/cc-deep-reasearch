"""Prompt templates for the backlog chat agent.

Contract Version: 1.0.0

The agent reads the current backlog snapshot and recent conversation,
gives concise editorial advice, and proposes structured backlog operations.

Output format: JSON only (see agents/backlog_chat.py for parsing contract).
"""

from __future__ import annotations

from cc_deep_research.content_gen.models import BacklogItem

CONTRACT_VERSION = "1.0.0"

GLOBAL_RULES = """\
You are a sharp editorial assistant for a short-form video content backlog.

Important:
- Be concise — give actionable advice, not lengthy explanations
- Propose only operations justified by the conversation
- Prefer updating existing items over creating duplicates
- Avoid destructive actions (archive, kill) unless clearly warranted
- Every operation must have a clear reason
- Return JSON only — no prose outside the JSON structure"""


BACKLOG_CHAT_SYSTEM = f"""\
{GLOBAL_RULES}

You are reviewing a content backlog and advising on improvements.

Your task:
1. Read the current backlog items and the recent conversation
2. Give concise editorial advice on what to tighten, clarify, or add
3. Propose specific backlog operations (update or create) when warranted
4. Do NOT write anything — only propose; the operator decides whether to apply

Output format — return ONLY this JSON structure, no additional text:

{{
  "reply_markdown": "Here is what I would focus on first...",
  "apply_ready": true,
  "warnings": ["any concerns about the proposals"],
  "operations": [
    {{
      "kind": "update_item",
      "idea_id": "abc12345",
      "reason": "why this change is needed",
      "fields": {{
        "field_name": "new value"
      }}
    }},
    {{
      "kind": "create_item",
      "reason": "why this new item is needed",
      "fields": {{
        "idea": "the idea text",
        "category": "authority-building",
        "audience": "who this is for",
        "problem": "the specific problem it solves"
      }}
    }}
  ],
  "mentioned_idea_ids": ["idea_id", "another_id"]
}}

Rules:
- reply_markdown should be 1-3 short sentences, editorial in tone
- apply_ready=true means you have concrete, justified proposals; false means just advisory
- warnings can flag risks (e.g., duplicate ideas, overly broad scope)
- operations.kind must be "update_item" or "create_item" only
- update_item requires idea_id and at least one field to change
- create_item requires idea in fields; other fields are optional
- mentioned_idea_ids lists all idea IDs referenced in your reply or operations
- If no operations are warranted, set operations=[] and apply_ready=false"""


def build_backlog_chat_user(
    messages: list[dict],
    backlog_items: list[BacklogItem],
    strategy: dict | None = None,
    selected_idea_id: str | None = None,
) -> str:
    """Build the user prompt for the backlog chat agent.

    Args:
        messages: List of {"role": "user"|"assistant", "content": str} messages
        backlog_items: Current backlog snapshot
        strategy: Optional strategy context
        selected_idea_id: Optional currently selected idea ID
    """
    parts = ["=== CONVERSATION ==="]

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        parts.append(f"[{role.upper()}] {content}")

    parts.append("")
    parts.append("=== CURRENT BACKLOG ===")

    if not backlog_items:
        parts.append("(empty backlog)")
    else:
        for item in backlog_items:
            status_marker = " [SELECTED]" if item.idea_id == selected_idea_id else ""
            parts.append("---")
            parts.append(f"idea_id: {item.idea_id}{status_marker}")
            parts.append(f"category: {item.category}")
            parts.append(f"idea: {item.idea}")
            parts.append(f"audience: {item.audience}")
            parts.append(f"problem: {item.problem}")
            if item.status:
                parts.append(f"status: {item.status}")
            if item.latest_score is not None:
                parts.append(f"score: {item.latest_score}")
            if item.potential_hook:
                parts.append(f"hook: {item.potential_hook}")
            if item.evidence:
                parts.append(f"evidence: {item.evidence}")

    if strategy:
        parts.append("")
        parts.append("=== STRATEGY ===")
        if strategy.get("niche"):
            parts.append(f"Niche: {strategy['niche']}")
        if strategy.get("content_pillars"):
            parts.append(f"Content pillars: {', '.join(strategy['content_pillars'])}")

    parts.append("")
    parts.append("Provide your response as JSON only.")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Field validation constants (shared with agent for server-side checks)
# ---------------------------------------------------------------------------

SUPPORTED_UPDATE_FIELDS = frozenset({
    "idea",
    "category",
    "audience",
    "problem",
    "source",
    "why_now",
    "potential_hook",
    "content_type",
    "evidence",
    "risk_level",
    "status",
    "selection_reasoning",
})

SUPPORTED_CREATE_FIELDS = frozenset({
    "idea",
    "category",
    "audience",
    "problem",
    "source",
    "why_now",
    "potential_hook",
    "content_type",
    "evidence",
    "risk_level",
})
