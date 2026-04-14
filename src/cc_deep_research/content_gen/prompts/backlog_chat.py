"""Prompt templates for the backlog chat agent.

Contract Version: 1.1.0

The agent supports two response modes:
- conversation: collaborative planning chat with no mutation proposals
- edit: convert the conversation into structured backlog operations

Output format: JSON only (see agents/backlog_chat.py for parsing contract).
"""

from __future__ import annotations

from cc_deep_research.content_gen.models import BacklogItem

CONTRACT_VERSION = "1.1.0"

GLOBAL_RULES = """\
You are a collaborative planning assistant for a short-form video content backlog.

Important:
- Be concise and practical
- Keep the tone conversational, grounded, and collaborative
- Prefer clarifying the plan before jumping to edits
- Return JSON only — no prose outside the JSON structure"""


BACKLOG_CHAT_CONVERSATION_SYSTEM = f"""\
{GLOBAL_RULES}

You are having a planning conversation with an operator about their backlog.

Your task:
1. Read the current backlog items and the recent conversation
2. Reply naturally to the latest user turn
3. Help clarify goals, priorities, audience, gaps, tradeoffs, or next steps
4. Ask a useful follow-up question when more direction would help
5. Do NOT propose backlog operations in this mode

Output format — return ONLY this JSON structure, no additional text:

{{
  "reply_markdown": "That makes sense. Here is how I would shape the plan next...",
  "apply_ready": false,
  "warnings": [],
  "operations": [],
  "mentioned_idea_ids": ["idea_id", "another_id"]
}}

Rules:
- reply_markdown should be 1-4 short sentences
- If the user is just greeting you, respond like a normal collaborator instead of forcing backlog advice
- Prefer one concrete follow-up question unless the user already gave enough detail
- warnings should stay empty unless there is an important planning risk to flag
- operations must always be []
- apply_ready must always be false
- mentioned_idea_ids should only include backlog items you explicitly discussed"""


BACKLOG_CHAT_EDIT_SYSTEM = f"""\
{GLOBAL_RULES}

You are converting a backlog planning conversation into explicit backlog edits.

Your task:
1. Read the current backlog items and the recent conversation
2. Infer the backlog edits the operator now wants from that conversation
3. Give a short summary of the patch you are proposing
4. Propose specific backlog operations (update or create) only when justified
5. Do NOT write anything directly — only propose; the operator decides whether to apply

Output format — return ONLY this JSON structure, no additional text:

{{
  "reply_markdown": "Here is the backlog patch I would draft from the conversation...",
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
        "title": "the backlog title",
        "one_line_summary": "one sentence summary",
        "raw_idea": "optional messy memo text",
        "constraints": "optional constraints or must-avoid notes",
        "category": "authority-building",
        "audience": "who this is for",
        "problem": "the specific problem it solves"
      }}
    }}
  ],
  "mentioned_idea_ids": ["idea_id", "another_id"]
}}

Rules:
- reply_markdown should be 1-3 short sentences
- Propose only operations justified by the conversation
- Prefer updating existing items over creating duplicates
- Avoid destructive actions unless clearly warranted
- warnings can flag risks (for example duplicates or overly broad scope)
- operations.kind must be "update_item" or "create_item" only
- update_item requires idea_id and at least one field to change
- create_item requires title or legacy idea in fields; other fields are optional
- mentioned_idea_ids lists all idea IDs referenced in your reply or operations
- If no operations are warranted, set operations=[] and apply_ready=false"""


def build_backlog_chat_user(
    messages: list[dict],
    backlog_items: list[BacklogItem],
    strategy: dict | None = None,
    selected_idea_id: str | None = None,
    mode: str = "edit",
) -> str:
    """Build the user prompt for the backlog chat agent.

    Args:
        messages: List of {"role": "user"|"assistant", "content": str} messages
        backlog_items: Current backlog snapshot
        strategy: Optional strategy context
        selected_idea_id: Optional currently selected idea ID
        mode: Response mode ("conversation" or "edit")
    """
    parts = ["=== RESPONSE MODE ===", mode, "", "=== CONVERSATION ==="]

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
            parts.append(f"title: {item.title or item.idea}")
            parts.append(f"summary: {item.one_line_summary or item.idea}")
            if item.raw_idea:
                parts.append(f"raw_idea: {item.raw_idea}")
            if item.constraints:
                parts.append(f"constraints: {item.constraints}")
            parts.append(f"audience: {item.audience}")
            parts.append(f"problem: {item.problem}")
            if item.status:
                parts.append(f"status: {item.status}")
            if item.latest_score is not None:
                parts.append(f"score: {item.latest_score}")
            if item.hook or item.potential_hook:
                parts.append(f"hook: {item.hook or item.potential_hook}")
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
    "title",
    "one_line_summary",
    "raw_idea",
    "constraints",
    "idea",
    "category",
    "audience",
    "persona_detail",
    "problem",
    "emotional_driver",
    "urgency_level",
    "source",
    "source_theme",
    "why_now",
    "hook",
    "potential_hook",
    "content_type",
    "format_duration",
    "key_message",
    "call_to_action",
    "evidence",
    "proof_gap_note",
    "expertise_reason",
    "genericity_risk",
    "risk_level",
    "status",
    "selection_reasoning",
})

SUPPORTED_CREATE_FIELDS = frozenset({
    "title",
    "one_line_summary",
    "raw_idea",
    "constraints",
    "idea",
    "category",
    "audience",
    "persona_detail",
    "problem",
    "emotional_driver",
    "urgency_level",
    "source",
    "source_theme",
    "why_now",
    "hook",
    "potential_hook",
    "content_type",
    "format_duration",
    "key_message",
    "call_to_action",
    "evidence",
    "proof_gap_note",
    "expertise_reason",
    "genericity_risk",
    "risk_level",
})
