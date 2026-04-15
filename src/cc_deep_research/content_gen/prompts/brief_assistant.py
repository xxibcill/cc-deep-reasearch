"""Prompt templates for the brief assistant agent.

Contract Version: 1.0.0

The agent supports two response modes:
- conversation: collaborative brief refinement with no mutation proposals
- edit: convert the conversation into structured brief revision proposals

Output format: JSON only (see agents/brief_assistant.py for parsing contract).
"""

from __future__ import annotations

from cc_deep_research.content_gen.models import BriefRevision

CONTRACT_VERSION = "1.0.0"

GLOBAL_RULES = """\
You are a collaborative editorial assistant for opportunity briefs.

Important:
- Be concise and practical
- Keep the tone conversational, grounded, and helpful
- Prefer clarifying intent before jumping to edits
- Return JSON only — no prose outside the JSON structure"""


BRIEF_ASSISTANT_CONVERSATION_SYSTEM = GLOBAL_RULES + """

You are having a refinement conversation with an operator about their opportunity brief.

You are having a refinement conversation with an operator about their opportunity brief.

Your task:
1. Read the current brief revision content and the recent conversation
2. Reply naturally to the latest user turn
3. Help clarify goals, audience, positioning, constraints, or gaps
4. Ask a useful follow-up question when more direction would help
5. Do NOT propose revisions in this mode

Output format — return ONLY this JSON structure, no additional text:

{{
  "reply_markdown": "That makes sense. Here's how I would think about the brief...",
  "apply_ready": false,
  "warnings": [],
  "proposals": [],
  "mentioned_fields": ["theme", "goal"]
}}

Rules:
- reply_markdown should be 1-4 short sentences
- If the user is just greeting you, respond like a normal collaborator instead of forcing advice
- Prefer one concrete follow-up question unless the user already gave enough detail
- warnings should stay empty unless there is an important risk to flag
- proposals must always be []
- apply_ready must always be false
- mentioned_fields should only include brief fields you explicitly discussed"""


BRIEF_ASSISTANT_EDIT_SYSTEM = GLOBAL_RULES + """

You are converting a brief refinement conversation into explicit revision proposals.

Your task:
1. Read the current brief revision and the recent conversation
2. Infer the revision the operator now wants from that conversation
3. Give a short summary of the revision you are proposing
4. Propose specific field changes only when justified
5. Do NOT write anything directly — only propose; the operator decides whether to apply

Output format — return ONLY this JSON structure, no additional text:

{{
  "reply_markdown": "Here is the brief revision I would draft from the conversation...",
  "apply_ready": true,
  "warnings": ["any concerns about the proposals"],
  "proposals": [
    {{
      "reason": "why this change is needed",
      "fields": {{
        "theme": "refined theme title",
        "goal": "updated goal statement"
      }}
    }}
  ],
  "mentioned_fields": ["theme", "goal"]
}}

Rules:
- reply_markdown should be 1-3 short sentences
- Propose only changes justified by the conversation
- Avoid destructive changes unless clearly warranted
- warnings can flag risks (for example overly broad scope or conflicting changes)
- proposals[].fields can include any OpportunityBrief fields
- mentioned_fields lists all brief fields referenced in your reply or proposals
- If no proposals are warranted, set proposals=[] and apply_ready=false"""


# Fields that can be proposed for revision
SUPPORTED_REVISION_FIELDS = frozenset({
    "theme",
    "goal",
    "primary_audience_segment",
    "secondary_audience_segments",
    "problem_statements",
    "content_objective",
    "proof_requirements",
    "platform_constraints",
    "risk_constraints",
    "freshness_rationale",
    "sub_angles",
    "research_hypotheses",
    "success_criteria",
    "expert_take",
    "non_obvious_claims_to_test",
    "genericity_risks",
})


def build_brief_assistant_user(
    messages: list[dict],
    brief_revision: BriefRevision | None,
    mode: str = "edit",
) -> str:
    """Build the user prompt for the brief assistant agent.

    Args:
        messages: List of {"role": "user"|"assistant", "content": str} messages
        brief_revision: Current brief revision snapshot
        mode: Response mode ("conversation" or "edit")
    """
    parts = ["=== RESPONSE MODE ===", mode, "", "=== CONVERSATION ==="]

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        parts.append(f"[{role.upper()}] {content}")

    parts.append("")
    parts.append("=== CURRENT BRIEF REVISION ===")

    if brief_revision is None:
        parts.append("(no brief revision loaded)")
    else:
        parts.append(f"revision_id: {brief_revision.revision_id}")
        parts.append(f"version: v{brief_revision.version}")
        parts.append(f"theme: {brief_revision.theme}")
        parts.append(f"goal: {brief_revision.goal}")
        parts.append(f"primary_audience_segment: {brief_revision.primary_audience_segment}")
        if brief_revision.secondary_audience_segments:
            parts.append(f"secondary_audience_segments: {', '.join(brief_revision.secondary_audience_segments)}")
        if brief_revision.problem_statements:
            parts.append("problem_statements:")
            for ps in brief_revision.problem_statements:
                parts.append(f"  - {ps}")
        parts.append(f"content_objective: {brief_revision.content_objective}")
        if brief_revision.proof_requirements:
            parts.append(f"proof_requirements: {', '.join(brief_revision.proof_requirements)}")
        if brief_revision.platform_constraints:
            parts.append(f"platform_constraints: {', '.join(brief_revision.platform_constraints)}")
        if brief_revision.risk_constraints:
            parts.append(f"risk_constraints: {', '.join(brief_revision.risk_constraints)}")
        if brief_revision.freshness_rationale:
            parts.append(f"freshness_rationale: {brief_revision.freshness_rationale}")
        if brief_revision.sub_angles:
            parts.append(f"sub_angles: {', '.join(brief_revision.sub_angles)}")
        if brief_revision.research_hypotheses:
            parts.append(f"research_hypotheses: {', '.join(brief_revision.research_hypotheses)}")
        if brief_revision.success_criteria:
            parts.append(f"success_criteria: {', '.join(brief_revision.success_criteria)}")
        if brief_revision.expert_take:
            parts.append(f"expert_take: {brief_revision.expert_take}")
        if brief_revision.non_obvious_claims_to_test:
            parts.append(f"non_obvious_claims_to_test: {', '.join(brief_revision.non_obvious_claims_to_test)}")
        if brief_revision.genericity_risks:
            parts.append(f"genericity_risks: {', '.join(brief_revision.genericity_risks)}")
        parts.append(f"revision_notes: {brief_revision.revision_notes}")

    parts.append("")
    parts.append("Provide your response as JSON only.")

    return "\n".join(parts)
