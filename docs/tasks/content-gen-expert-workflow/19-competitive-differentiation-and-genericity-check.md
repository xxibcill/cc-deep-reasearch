# Task 19: Add Competitive Differentiation And Genericity Check

Status: Completed

Goal:
Make the workflow explicitly compare its chosen angle and script against common market framing so it can avoid generic takes and defend a more distinctive editorial position.

Primary files:
- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/agents/research_pack.py`
- `src/cc_deep_research/content_gen/agents/argument_map.py`
- `src/cc_deep_research/content_gen/agents/quality_evaluator.py`

Scope:
- Retrieve or synthesize a compact view of common competitor narratives, repeated clichés, and expected talking points for the chosen topic.
- Add fields that capture differentiation strategy, genericity risks, and "sounds like everyone else" failure modes.
- Require the argument map or evaluator to state what the selected angle challenges, reframes, or contributes beyond standard advice.
- Make genericity or undifferentiated framing a first-class quality concern, not just a vague suggestion.

Implementation notes:
- Keep the comparison lightweight; this is a differentiation check, not a full competitor-intelligence subsystem.
- Favor patterns and framing overlap over brittle exact text matching.
- Preserve room for convergent truths; the goal is not to force novelty for its own sake when consensus is correct.

Acceptance criteria:
- The workflow can describe why an angle is distinct from the baseline market framing for the same topic.
- Evaluator feedback can explicitly flag cliché framing or interchangeable takes.
- Differentiation data is available before final scripting so the system can course-correct early.

Validation:
- Add tests for genericity-risk detection and differentiation-field parsing.
- Add at least one fixture showing a bland angle being flagged against common market framing.

Out of scope:
- Full competitor account monitoring
- Social scraping beyond the current retrieval capabilities
