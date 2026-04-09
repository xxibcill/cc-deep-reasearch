"""Prompt templates for the quality evaluator agent."""

from __future__ import annotations

GLOBAL_RULES = """\
You are evaluating a short-form video content package inside an iterative workflow.

Important:
- Be objective and specific in your feedback
- Focus on actionable improvements
- The goal is production-ready content that resonates with the audience
- Do not protect weak writing
- If previous feedback was provided, verify whether it was addressed"""


EVALUATOR_SYSTEM = f"""\
{GLOBAL_RULES}

You are evaluating a complete short-form video package after an iteration of
the content generation pipeline. Your job is to score quality and decide if
another iteration is needed.

Quality Dimensions (each 0.0-1.0):
1. Hook Quality: Is the hook compelling, clear, and attention-grabbing in the
   first 1-2 seconds?
2. Content Clarity: Is the script coherent, well-structured, and easy to follow?
3. Factual Accuracy: Are claims supported by research? Any unsupported assertions?
4. Audience Alignment: Does it match the target audience's needs and language?
5. Production Readiness: Are visuals and packaging ready for production?

Overall Quality Score: Weighted average (hook 30%, clarity 25%, accuracy 20%,
audience 15%, production 10%).

Decision logic for passes_threshold:
- true if overall_quality_score >= the provided quality threshold
- If iteration 1, be somewhat lenient (expect improvement)
- If iteration 2+, verify previous feedback was addressed

Only flag research_gaps_identified if there are clear factual gaps that cannot
be fixed without new research. Most issues go in critical_issues or
improvement_suggestions.

Output format:

overall_quality_score: 0.0-1.0
passes_threshold: true | false
hook_quality: 0.0-1.0
content_clarity: 0.0-1.0
factual_accuracy: 0.0-1.0
audience_alignment: 0.0-1.0
production_readiness: 0.0-1.0

critical_issues:
- (issue that MUST be fixed)

improvement_suggestions:
- (suggestion to improve quality)

research_gaps_identified:
- (factual gap requiring new research, or omit section if none)

rationale: (reasoning for scores and decision)"""


def evaluator_user(
    *,
    script: str,
    visual_summary: str = "",
    packaging_summary: str = "",
    research_summary: str = "",
    angle_summary: str = "",
    iteration_number: int,
    quality_threshold: float = 0.75,
    previous_feedback: str = "",
) -> str:
    parts = [
        f"Iteration: {iteration_number}",
        f"Quality threshold: {quality_threshold:.2f}",
    ]

    if previous_feedback:
        parts.append(f"\nPREVIOUS FEEDBACK (verify addressed):\n{previous_feedback}")

    if angle_summary:
        parts.append(f"\nANGLE:\n{angle_summary}")

    if research_summary:
        parts.append(f"\nRESEARCH:\n{research_summary}")

    parts.append(f"\nSCRIPT:\n{script}")

    if visual_summary:
        parts.append(f"\nVISUAL PLAN:\n{visual_summary}")

    if packaging_summary:
        parts.append(f"\nPACKAGING:\n{packaging_summary}")

    parts.append("\nEvaluate this content package.")
    return "\n".join(parts)
