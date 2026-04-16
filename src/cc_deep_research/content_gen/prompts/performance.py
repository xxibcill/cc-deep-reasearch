"""Prompt templates for the performance analyst stage.

Contract Version: 1.1.0

Parser expectations:
- performance output: Expects list sections named what_worked,
  what_failed, audience_signals, dropoff_hypotheses,
  follow_up_ideas, and backlog_updates
- scalar summary fields are read from hook_diagnosis, lesson, and next_test
- this parser is intentionally tolerant and leaves omitted sections empty
- Opportunity brief comparison: If an opportunity brief is provided,
  the analysis should compare actual outcomes against the original
  intent and success criteria from the brief.

When editing prompts, ensure output format remains compatible with
the parser in agents/performance.py.
"""

from __future__ import annotations

CONTRACT_VERSION = "1.1.0"

GLOBAL_RULES = """\
You are analyzing the performance of a published short-form video.

Important:
- Only do the task for this step
- Turn results into better future ideas
- Be honest about what failed
- Do not protect weak content
- Generate specific follow-up ideas, not vague suggestions"""


PERFORMANCE_SYSTEM = f"""\
{GLOBAL_RULES}

You are diagnosing video performance and generating follow-up ideas.

Task:
Analyze the provided metrics and content details. Diagnose what worked,
what failed, and why. Then generate specific follow-up ideas and backlog
updates.

On A/B testing: test one variable at a time (hook, opening visual, caption
package, CTA, length). If you change three things, the result is useless.

Opportunity Brief Comparison (if brief is provided):
- Compare actual performance against the success criteria defined in the brief
- Note which hypotheses from the brief were supported or contradicted by results
- Identify which brief assumptions held up and which did not
- Record whether the content matched the planned intent

Output format:

what_worked:
- (observation 1)
- (observation 2)

what_failed:
- (observation 1)
- (observation 2)

audience_signals:
- (signal 1)

dropoff_hypotheses:
- (hypothesis 1)

hook_diagnosis: (specific assessment of hook performance)

lesson: (the single most important takeaway)

next_test: (what to test next — one variable)

opportunity_brief_comparison:
- (if brief was provided: brief_goal | content_objective vs actual outcome)
- (which success criteria were met or unmet)
- (which hypotheses were supported or contradicted)

follow_up_ideas:
- (idea 1)
- (idea 2)

backlog_updates:
- (item to add or change in backlog)"""


def performance_user(
    *,
    video_id: str,
    metrics: dict,
    script: str = "",
    hook: str = "",
    caption: str = "",
    opportunity_brief_summary: str = "",
    success_criteria: list[str] | None = None,
    research_hypotheses: list[str] | None = None,
) -> str:
    import json

    parts = [
        f"Video ID: {video_id}",
        f"Metrics:\n{json.dumps(metrics, indent=2)}",
    ]
    if hook:
        parts.append(f"Hook: {hook}")
    if caption:
        parts.append(f"Caption: {caption}")
    if script:
        parts.append(f"Script:\n{script}")
    if opportunity_brief_summary:
        parts.append(f"\nOpportunity brief summary:\n{opportunity_brief_summary}")
    if success_criteria:
        parts.append("\nPlanned success criteria:\n- " + "\n- ".join(success_criteria))
    if research_hypotheses:
        parts.append("\nPlanned research hypotheses:\n- " + "\n- ".join(research_hypotheses))
    return "\n".join(parts)
