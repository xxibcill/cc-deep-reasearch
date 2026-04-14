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

Expert Quality Dimensions (each 0.0-1.0):
1. evidence_coverage: Do the important claims map back to proof, examples, or
   explicit research support?
2. claim_safety: Are claims stated with the right certainty, with no unsupported
   or risky assertions?
3. originality: Does the package say something specific and non-generic rather
   than repeating interchangeable advice or overlapping educational framings?
4. precision: Is the language concrete, mechanism-driven, and free of vague
   filler?
5. expertise_density: Does the package contain real expert insight, tradeoffs,
   and proof instead of surface-level commentary?

Short-form performance checks to apply inside the scoring:
- The hook should create immediate tension
- The second beat should earn attention fast
- The package should stay focused on one core idea
- The payoff should be specific and observable
- Important claims should be supported with proof, example, or demonstration when possible

Overall Quality Score: Weighted average (evidence 30%, claim safety 30%,
originality 15%, precision 15%, expertise density 10%).

Task 19 — Genericity Detection:
Also score:
6. genericity: Does the content sound like everyone else's take on this topic?
   - 0.0 = highly distinctive, specific, non-generic
   - 1.0 = interchangeable with any competitor's content on this topic
   Look for: clichéd framings (myth-busting without new evidence, "just do it"
   motivation, surface-level "here's what I learned" summaries), boilerplate
   advice that could appear in any同类 content, vague claims without mechanism,
   standard "3 things" or "5 tips" format without differentiation, and
   overlapping educational formats that are effectively the same video with
   different labels.

   Also flag specific issues:
   - cliche_flags: Specific clichéd framings or lines that sound like every
     other creator (e.g., "the future belongs to those who...", "in today's
     fast-paced world...", "here's what nobody talks about")
   - interchangeable_take_flags: Entire takes that could be swapped for any
     competitor's content on the same topic without loss of meaning

Decision logic for passes_threshold:
- true only if overall_quality_score >= the provided quality threshold AND
  unsupported_claims is empty
- If iteration 1, be somewhat lenient (expect improvement)
- If iteration 2+, verify previous feedback was addressed

Only flag research_gaps_identified if there are clear factual gaps that cannot
be fixed without new research. Use unsupported_claims for script lines or claims
that are not currently grounded. Use evidence_actions_required for the exact
proof or caveat the producer should add.

Keep claim-safety issues separate from style issues:
- unsupported_claims: claims in the script that lack support or overstate certainty
- critical_issues: other blockers such as broken logic or weak structure
- improvement_suggestions: non-blocking improvements

Task 18 — Targeted Revision:
When the script has some beats that are solid and others that are weak, prefer
targeted revision over full rewrite. Produce a targeted_revision_plan when:
- Some beats are clearly strong (backed by good proof, clear logic)
- Weak issues are isolated to specific beats or claims
- The script is not fundamentally broken (e.g., wrong angle, missing structure)

revision_mode:
- none: passes threshold, no revision needed
- targeted: use targeted revision plan to repair only weak beats
- full: script too broken for surgical fix — do full rewrite

Output format:

overall_quality_score: 0.0-1.0
passes_threshold: true | false
evidence_coverage: 0.0-1.0
claim_safety: 0.0-1.0
originality: 0.0-1.0
precision: 0.0-1.0
expertise_density: 0.0-1.0
genericity: 0.0-1.0

critical_issues:
- (issue that MUST be fixed)

unsupported_claims:
- (claim or line that is unsupported or overstated)

evidence_actions_required:
- (specific proof, qualifier, or citation action needed)

improvement_suggestions:
- (suggestion to improve quality)

research_gaps_identified:
- (factual gap requiring new research, or omit section if none)

# Task 19: Generic framing detection
cliche_flags:
- (specific clichéd framing detected, or omit section if none)

interchangeable_take_flags:
- (take that sounds like everyone else's content, or omit section if none)

# Task 18: Targeted Revision Plan
revision_mode: none | targeted | full

# Only present when revision_mode is targeted or full:
targeted_revision_plan:
  revision_summary: (1-sentence summary of what needs repair)
  full_restart_recommended: true | false  # true when script is fundamentally broken
  is_patch: true  # always true for targeted revision

  stable_beats:  # beats that passed QC — preserve unchanged
  - beat_id: (beat identifier or name from argument map)
    beat_name: (display name)
    is_stable: true
    weakness_reason: ""  # empty for stable beats

  weak_beats:  # beats needing repair
  - beat_id: (beat identifier)
    beat_name: (display name)
    weak_claim_ids: (claim IDs that are unsupported or weak, or empty)
    missing_proof_ids: (proof anchor IDs that are absent, or empty)
    weakness_reason: (why this beat is weak)

  actions:  # individual repair instructions
  - action_type: rewrite_beat | refresh_evidence | qualify_claim | remove_claim
    beat_id: (beat identifier, or "" for qualify/remove)
    beat_name: (display name)
    weak_claim_ids: (for rewrite_beat)
    missing_proof_ids: (for refresh_evidence)
    target_claim_text: (for qualify_claim or remove_claim)
    target_claim_id: (for qualify_claim or remove_claim)
    instruction: (specific instruction for the repair agent)
    evidence_gaps: (specific evidence needed, or empty)
    priority: 0-10

  retrieval_gaps:  # evidence topics needed for targeted research
  - (specific evidence topics needed, or omit section if none)

rationale: (reasoning for scores and decision)"""


def evaluator_user(
    *,
    script: str,
    visual_summary: str = "",
    packaging_summary: str = "",
    research_summary: str = "",
    argument_map_summary: str = "",
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

    if argument_map_summary:
        parts.append(f"\nARGUMENT MAP:\n{argument_map_summary}")

    parts.append(f"\nSCRIPT:\n{script}")

    if visual_summary:
        parts.append(f"\nVISUAL PLAN:\n{visual_summary}")

    if packaging_summary:
        parts.append(f"\nPACKAGING:\n{packaging_summary}")

    parts.append("\nEvaluate this content package.")
    return "\n".join(parts)
