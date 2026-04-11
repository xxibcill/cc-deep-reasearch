# Task 15: Redesign Retrieval Planning Beyond Fixed Query Families

Status: Done

Goal:
Move research-pack retrieval from a small fixed query-family set to a broader fanout strategy that adapts to the idea, angle, evidence gaps, and prior failures.

Primary files:
- `src/cc_deep_research/content_gen/agents/research_pack.py`
- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/orchestrator.py`

Scope:
- Replace or extend the fixed query-family builder with a retrieval planner that can vary depth and breadth intentionally.
- Allow fanout decisions to use context such as:
  - proof requirements
  - missing or weak evidence from prior passes
  - freshness needs
  - contrarian or counterevidence coverage
- Keep provider usage bounded and observable; do not explode into arbitrary search volume.

Implementation notes:
- This is a planning redesign, not just adding more static query strings.
- Preserve current provenance tracking and source deduplication.
- Prefer explicit retrieval budgets and stop rules so costs remain understandable.

Acceptance criteria:
- Retrieval planning is no longer just a small hard-coded family list. ✓
- The planner can widen or narrow search behavior based on content needs. ✓
- Query provenance and source retention still work after the redesign. ✓
- Iterative reruns can request more targeted retrieval instead of repeating the same baseline plan. ✓

Validation:
- Add unit tests for retrieval planning decisions and budget behavior. ✓ (21 tests added)
- Add research-pack tests that verify provenance survives broader fanout. ✓ (existing test passes)

Out of scope:
- New external search providers
- Full autonomous research loops without operator-visible budgets

Implementation summary:
- Added `RetrievalMode`, `RetrievalDecision`, `RetrievalBudget`, and `RetrievalPlan` models to `models.py`
- Added `RetrievalPlanner` class to `research_pack.py` with modes: BASELINE, DEEP, TARGETED, CONTRARIAN
- Updated `ResearchPackAgent.build` to accept `research_gaps` parameter and use the planner
- Updated `_stage_build_research_pack` in orchestrator to extract and pass `research_gaps` from quality evaluation
- Added 21 unit tests for retrieval planning decisions and budget behavior
