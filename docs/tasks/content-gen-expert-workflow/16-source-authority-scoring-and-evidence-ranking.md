# Task 16: Add Source Authority Scoring And Evidence Ranking

Status: Done

Goal:
Teach the expert workflow to rank evidence by authority, directness, freshness, and relevance so downstream stages rely more heavily on the strongest sources instead of treating all retrieved support as roughly equal.

Primary files:
- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/agents/research_pack.py`
- `src/cc_deep_research/content_gen/orchestrator.py`
- `src/cc_deep_research/content_gen/prompts/research_pack.py`

Scope:
- Add structured source-quality fields such as source authority, evidence directness, freshness, and confidence.
- Rank or bucket retained sources before research synthesis and preserve the ranking in the resulting research pack.
- Prefer primary sources, original data, and highly direct evidence when selecting what to pass downstream.
- Surface weak-source warnings when the strongest available support is indirect, stale, anonymous, or low-confidence.

Implementation notes:
- Build on the provenance work from tasks 03 and 15 instead of introducing a separate source catalog shape.
- Keep ranking explainable and testable; avoid opaque one-number magic if a few explicit factors are enough.
- Do not force the system to discard all weak evidence; it should still be able to say "this is the best available support, but it is weak."

Acceptance criteria:
- Research-pack source records carry explicit quality metadata instead of only descriptive provenance.
- The synthesis input makes source quality visible enough for the model and parser to distinguish strong evidence from weak evidence.
- Downstream stages can identify when a claim is supported only by low-authority or indirect evidence.

Validation:
- Add focused tests for source-quality scoring, ranking, and retention behavior.
- Add at least one test that verifies a strong primary source outranks weaker secondary summaries for the same claim area.

Out of scope:
- New external search providers
- Human editorial approval policies
