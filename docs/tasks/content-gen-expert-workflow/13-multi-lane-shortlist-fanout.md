# Task 13: Expand Multi-Lane Execution Beyond The Primary Lane

Status: Planned

Goal:
Move the pipeline from a strict single-lane winner flow to a small queue-driven editorial planner that can execute more than the primary lane.

Primary files:
- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/orchestrator.py`
- `src/cc_deep_research/content_gen/backlog_service.py`

Scope:
- Allow the pipeline to carry more than one shortlisted idea forward in a controlled way.
- Start small: execute fanout across the top 2 ideas, not arbitrary breadth.
- Preserve one clearly marked primary candidate while keeping runner-ups alive.
- Define how angle, research, scripting, and publish artifacts are isolated per lane.

Implementation notes:
- This should build on the existing active-candidate queue instead of replacing it.
- Prefer explicit context structures over overloading `selected_idea_id`.
- Keep publish and backlog status transitions coherent.
- Do not hide lane behavior behind opaque abstractions; the orchestration flow should stay readable.

Acceptance criteria:
- The pipeline can execute more than one candidate lane without breaking existing single-idea behavior.
- Status tracking remains correct for selected, in-production, and runner-up items.
- Stage outputs remain attributable to the correct lane.
- Resume semantics are explicit for partial multi-lane runs.

Validation:
- Add orchestrator, backlog-service, and context-roundtrip tests for multi-lane behavior.

Out of scope:
- Unlimited branch exploration
- Dashboard redesign for multi-branch visualization
