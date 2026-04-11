# Task 18: Add Targeted Revision Loop For Weak Beats

Status: Done

Goal:
Replace broad whole-script reruns with a more surgical revision loop that repairs only the beats, claims, or proof gaps identified as weak by evaluation or QC.

Primary files:
- `src/cc_deep_research/content_gen/iterative_loop.py`
- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/orchestrator.py`
- `src/cc_deep_research/content_gen/agents/research_pack.py`
- `src/cc_deep_research/content_gen/agents/scripting.py`

Scope:
- Convert evaluator and QC findings into structured rewrite actions tied to specific beats or claim groups.
- Allow targeted retrieval or argument-map refreshes only for evidence gaps that actually matter.
- Re-run only the affected scripting steps or beat sections when the rest of the script is already acceptable.
- Preserve unchanged strong beats so revision loops do not repeatedly degrade good material.

Implementation notes:
- This task should build on retrieval gaps from task 15 and traceability from task 17 rather than inventing a second remediation system.
- Keep the operator-visible behavior understandable; selective revision should not feel like hidden state mutation.
- Avoid over-optimizing for partial rewrites if the current script is fundamentally broken and a full restart is cleaner.

Acceptance criteria:
- The iterative loop can issue targeted repair actions instead of only broad feedback blobs.
- Weak evidence or unsafe-claim findings can trigger narrow retrieval and rewrite passes without rebuilding the whole script by default.
- Successful beats remain stable across targeted revisions unless a dependency changed.

Validation:
- Add loop-behavior tests for targeted beat repair and selective retrieval refresh.
- Add regression coverage showing that localized revisions preserve unrelated high-quality beats.

Out of scope:
- Human-in-the-loop revision UI
- Autonomous unlimited self-rewrite loops
