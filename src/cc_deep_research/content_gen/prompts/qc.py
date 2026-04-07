"""Prompt templates for the human QC gate stage.

Contract Version: 1.0.0

Parser expectations:
- review output: Expects "QC Review:" section with check results,
  "Weakest parts:" numbered list, "Final Script:" section

When editing prompts, ensure output format remains compatible with
the parser in agents/qc.py.
"""

from __future__ import annotations

CONTRACT_VERSION = "1.0.0"

GLOBAL_RULES = """\
You are performing quality control on a short-form video package inside a modular workflow.

Important:
- Only do the task for this step
- This is an AI-assisted review — the human makes the final call
- Never auto-approve — always flag issues
- Be direct about problems
- Do not protect weak writing"""


QC_SYSTEM = f"""\
{GLOBAL_RULES}

You are reviewing a complete short-form video package before human approval.

Task:
Evaluate the package against the checklist below. You are an AI assistant
flagging issues for the human reviewer. You must not approve for publish —
that decision belongs to the human.

Checklist:
- Is the hook clear in the first 1-2 seconds?
- Is there any factual nonsense or unverified claims?
- Is there weak or generic wording?
- Are captions readable?
- Do visuals support the point?
- Is audio direction clear?
- Is the CTA appropriate?
- Is there any brand or legal risk?

Output format:

hook_strength: strong | adequate | weak
clarity_issues:
- (issue 1)

factual_issues:
- (issue 1)

visual_issues:
- (issue 1)

audio_issues:
- (issue 1)

caption_issues:
- (issue 1)

must_fix_items:
- (item 1)

Note: approved_for_publish is always false until a human sets it."""


def qc_user(
    *,
    script: str,
    visual_summary: str = "",
    packaging_summary: str = "",
) -> str:
    parts = [f"Script:\n{script}"]
    if visual_summary:
        parts.append(f"\nVisual plan summary:\n{visual_summary}")
    if packaging_summary:
        parts.append(f"\nPackaging summary:\n{packaging_summary}")
    return "\n".join(parts)
