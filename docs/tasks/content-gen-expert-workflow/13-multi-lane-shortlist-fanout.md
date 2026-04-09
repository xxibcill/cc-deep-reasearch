# Task 13: Optional Multi-Lane Shortlist Fanout

Goal:
Move the pipeline from a strict single-lane winner flow to a small queue-driven editorial planner.

Primary files:
- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/orchestrator.py`
- `src/cc_deep_research/content_gen/backlog_service.py`

Scope:
- Allow the pipeline to carry more than one shortlisted idea forward in a controlled way.
- Start small: support fanout across the top 2 ideas, not arbitrary breadth.
- Preserve one clearly marked primary candidate while keeping runner-ups alive.

Implementation notes:
- This is optional and should come after the expert-quality core is stable.
- Prefer explicit context structures over overloading `selected_idea_id`.
- Keep publish and backlog status transitions coherent.

Acceptance criteria:
- The pipeline can represent a small set of active candidate ideas without breaking existing single-idea behavior.
- Status tracking remains correct for selected, in-production, and runner-up items.
- The orchestrator code remains readable; do not hide the fanout in clever abstractions.

Validation:
- Add orchestrator and backlog-service tests for fanout behavior.

Out of scope:
- Unlimited branch exploration
- Dashboard redesign for multi-branch visualization

