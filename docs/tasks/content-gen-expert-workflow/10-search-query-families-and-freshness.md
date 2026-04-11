# Task 10: Improve Search Query Families And Freshness Logic

Status: Done

Goal:
Replace narrow heuristic searches with expert-oriented retrieval families and remove stale year-pinned logic.

Primary files:
- `src/cc_deep_research/content_gen/agents/research_pack.py`

Scope:
- Replace `_build_search_queries()` with labeled query families such as proof, primary-source, competitor, contrarian, freshness, and practitioner-language.
- Use current-year or year-agnostic freshness logic instead of hard-coded `2025`.
- Keep `max_queries` behavior intact while making query selection more intentional.

Implementation notes:
- Query families should reflect retrieval purpose, not just string variation.
- Prefer queries that can surface strong sources over generic trend chatter.
- If useful, include the query family in synthesized search context.

Acceptance criteria:
- The search query builder no longer contains stale year constants.
- Queries are diverse enough to retrieve evidence, counterevidence, and competitor framing.
- Query intent is visible in the code and easy to test.

Validation:
- Add unit tests for query generation and freshness behavior.

Out of scope:
- Research pack parser redesign
- Pipeline fanout
