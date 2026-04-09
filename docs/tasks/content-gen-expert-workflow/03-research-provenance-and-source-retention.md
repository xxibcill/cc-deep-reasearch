# Task 03: Preserve Retrieval Provenance In Research Output

Goal:
Stop collapsing search results into anonymous snippets. The research stage should retain enough source metadata to support expert claims.

Primary files:
- `src/cc_deep_research/content_gen/agents/research_pack.py`
- `src/cc_deep_research/content_gen/models.py`

Scope:
- Capture URL, title, provider, query, query family, and any useful source metadata from search results.
- Add a place on `ResearchPack` for raw or normalized supporting sources.
- Change `_run_searches()` so the synthesis prompt receives source-rich context instead of only title plus truncated content.
- Keep result volume bounded; do not dump huge raw pages into prompts.

Implementation notes:
- Reuse existing provenance data already available on `SearchResultItem` where possible.
- Favor normalized source records over freeform blobs.
- Make it obvious which claims are backed by which sources.

Acceptance criteria:
- A research pack can retain source provenance for at least the strongest retrieved evidence.
- The synthesis prompt input includes source identifiers that can be echoed back in parsed output.
- No hard-coded year strings should be added in this task.

Validation:
- Add a focused test that verifies provenance survives `_run_searches()` into the synthesized research shape.

Out of scope:
- New argument-map stage
- Search query family redesign

