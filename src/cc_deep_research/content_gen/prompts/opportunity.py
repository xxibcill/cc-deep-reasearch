"""Prompt templates for the opportunity planning stage.

Contract Version: 1.1.0

Parser expectations:
- Primary: JSON output with a tightly scoped schema (structured mode).
- Fallback: Header-based text format with exact scalar headers and '-' list sections
  (legacy mode). Used when JSON parsing fails or LLM reverts to text.
- Parse path is recorded in stage trace metadata via 'parse_mode' field.
- The parser fails fast when Goal, Primary audience segment,
  Problem statements, or Content objective are missing in either mode.

Structured output schema (preferred):
- All fields map 1:1 to OpportunityBrief model fields
- Scalar fields: theme, goal, primary_audience_segment, content_objective,
  freshness_rationale, expert_take
- List fields: secondary_audience_segments, problem_statements,
  proof_requirements, platform_constraints, risk_constraints,
  sub_angles, research_hypotheses, success_criteria,
  non_obvious_claims_to_test, genericity_risks
- Output MUST be valid JSON wrapped in ```json ... ``` code fences
- Empty lists are allowed; missing required scalars are not

Legacy text format (fallback):
- plan output: Expects exact scalar headers "Theme:", "Goal:",
  "Primary audience segment:", "Content objective:", and
  "Freshness rationale:"
- list sections are parsed from "-" items under:
  Secondary audience segments, Problem statements, Proof requirements,
  Platform constraints, Risk constraints, Sub-angles,
  Research hypotheses, Success criteria

When editing prompts, ensure output format remains compatible with
the parser in agents/opportunity.py.
"""

from __future__ import annotations

from cc_deep_research.content_gen.models import StrategyMemory

CONTRACT_VERSION = "1.1.0"

GLOBAL_RULES = """\
You are planning a short-form content opportunity inside a modular workflow.

Important:
- Only do the task for this step
- Be precise and ruthless about weak themes
- If a theme is too vague, call that out explicitly
- Do not invent facts, examples, or proof
- Keep every field concrete and actionable"""

PLAN_OPPORTUNITY_SYSTEM = f"""\
{GLOBAL_RULES}

You are turning a raw content theme into a structured opportunity brief.

Task:
Analyze the theme and produce a focused editorial contract that will guide
backlog generation, research, and scoring downstream.

Requirements:
- The goal must be specific and measurable
- Audience segments must be concrete (not "everyone" or "marketers")
- Problem statements must be real, observable problems
- Platform constraints should reflect short-form video realities
- Risk constraints should flag claims that need proof
- Sub-angles should be distinct editorial directions, not restatements
- Research hypotheses should be testable claims, not wishes
- Success criteria should be measurable outcomes

Output format — respond ONLY with a valid JSON object wrapped in ```json ... ```:

```json
{{
  "theme": "(refined theme statement)",
  "goal": "(specific content goal)",
  "primary_audience_segment": "(who this is really for)",
  "secondary_audience_segments": ["(segment 1)", "(segment 2)"],
  "problem_statements": ["(problem 1)", "(problem 2)"],
  "content_objective": "(what the content should accomplish)",
  "proof_requirements": ["(requirement 1)", "(requirement 2)"],
  "platform_constraints": ["(constraint 1)", "(constraint 2)"],
  "risk_constraints": ["(risk 1)", "(risk 2)"],
  "freshness_rationale": "(why this is timely now)",
  "sub_angles": ["(angle 1)", "(angle 2)", "(angle 3)"],
  "research_hypotheses": ["(hypothesis 1)", "(hypothesis 2)"],
  "success_criteria": ["(criterion 1)", "(criterion 2)"],
  "expert_take": "(optional: non-obvious insight from the expert angle)",
  "non_obvious_claims_to_test": ["(optional: claim 1)", "(optional: claim 2)"],
  "genericity_risks": ["(optional: risk 1)", "(optional: risk 2)"]
}}
```

Rules:
- Output ONLY the JSON object inside the code fence — no extra text before or after
- Use empty arrays [] for any list field that has no entries
- Do not omit any required field; use empty string "" for missing scalar values
- The JSON must be parseable by Python's json.loads()
"""


def plan_opportunity_user(
    theme: str,
    strategy: StrategyMemory,
) -> str:
    parts = [f"Theme: {theme}"]
    if strategy.niche:
        parts.append(f"Niche: {strategy.niche}")
    if strategy.content_pillars:
        parts.append(f"Content pillars: {', '.join(strategy.content_pillars)}")
    if strategy.audience_segments:
        segs = "; ".join(f"{s.name}: {s.description}" for s in strategy.audience_segments)
        parts.append(f"Known audience segments: {segs}")
    if strategy.tone_rules:
        parts.append(f"Tone rules: {', '.join(strategy.tone_rules)}")
    if strategy.forbidden_claims:
        parts.append(f"Forbidden claims: {', '.join(strategy.forbidden_claims)}")
    if strategy.proof_standards:
        parts.append(f"Proof standards: {', '.join(strategy.proof_standards)}")
    if strategy.platforms:
        parts.append(f"Target platforms: {', '.join(strategy.platforms)}")
    if strategy.past_winners:
        winners = "; ".join(w.title for w in strategy.past_winners[:5])
        parts.append(f"Past winners: {winners}")
    if strategy.past_losers:
        losers = "; ".join(loser.title for loser in strategy.past_losers[:5])
        parts.append(f"Past losers: {losers}")
    return "\n".join(parts)
