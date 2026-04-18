"""Prompt templates for the human QC gate stage.

Contract Version: 1.2.0

Parser expectations:
- review output: Expects `hook_strength:` plus issue buckets named
  clarity_issues, factual_issues, visual_issues, audio_issues,
  caption_issues, unsupported_claims, risky_claims, required_fact_checks,
  and must_fix_items. Each issue bucket is parsed as a "- " or "* " list.
  `approved_for_publish` is never parsed from model output.
- If success criteria from the opportunity brief are provided, the QC
  should evaluate whether the script satisfies each criterion and flag
  any criteria that are not met.

When editing prompts, ensure output format remains compatible with
the parser in agents/qc.py.
"""

from __future__ import annotations

CONTRACT_VERSION = "1.2.0"

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
- Is the hook clear and sharp in the first roughly 3 seconds?
- Does the second beat clarify the hook or create momentum instead of stalling in setup?
- Is there any factual nonsense, unsupported claim, or overstated certainty?
- Is there weak or generic wording?
- Is the payoff specific, not generic?
- Does the package stay on one core idea instead of stacking random advice?
- Is there proof, example, comparison, or concrete specificity where the claim needs it?
- Are captions readable?
- Do visuals support the point?
- Is audio direction clear?
- Is the CTA appropriate?
- Is there any brand or legal risk?

If research or argument-map context is provided, compare the script against it.
Call out:
- unsupported_claims for lines that are not grounded by the provided context
- risky_claims for legal, trust, reputational, or medical/financial-style risk
- required_fact_checks for checks a human must verify before publish

Put severe unsupported or risky claims into must_fix_items too.
If the first two beats are weak or slow, include that in must_fix_items.

Success Criteria Evaluation (if criteria are provided):
- For each success criterion, evaluate whether the script satisfies it
- If a criterion is not satisfied, note it in clarity_issues or factual_issues
- Record which criteria are met and which are not in the output

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

unsupported_claims:
- (unsupported or overstated claim)

risky_claims:
- (claim with legal, trust, or reputational risk)

required_fact_checks:
- (specific fact check the human reviewer must perform)

must_fix_items:
- (item 1)

success_criteria_evaluation:
- (if criteria were provided: list each criterion and whether it is met or unmet)

Note: approved_for_publish is always false until a human sets it."""


def qc_user(
    *,
    script: str,
    visual_summary: str = "",
    packaging_summary: str = "",
    research_summary: str = "",
    argument_map_summary: str = "",
    success_criteria: list[str] | None = None,
) -> str:
    parts = [f"Script:\n{script}"]
    if research_summary:
        parts.append(f"\nResearch summary:\n{research_summary}")
    if argument_map_summary:
        parts.append(f"\nArgument map summary:\n{argument_map_summary}")
    if visual_summary:
        parts.append(f"\nVisual plan summary:\n{visual_summary}")
    if packaging_summary:
        parts.append(f"\nPackaging summary:\n{packaging_summary}")
    if success_criteria:
        parts.append("\nSuccess criteria to evaluate:\n- " + "\n- ".join(success_criteria))
    return "\n".join(parts)
