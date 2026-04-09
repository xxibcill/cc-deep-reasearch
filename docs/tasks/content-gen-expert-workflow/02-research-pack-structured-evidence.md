# Task 02: Replace Flat Research Pack Lists With Structured Evidence

Goal:
Upgrade the research pack contract from loose string lists to typed evidence records that downstream stages can reason over.

Primary files:
- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/prompts/research_pack.py`
- `src/cc_deep_research/content_gen/agents/research_pack.py`

Scope:
- Introduce typed models for claims, proof points, source-backed findings, counterpoints, and uncertainty flags.
- Redesign `ResearchPack` so it can retain structured evidence instead of only string lists.
- Update the research-pack prompt contract to request machine-parseable sections that map cleanly to the new models.
- Update the parser accordingly.

Implementation notes:
- Prefer a v2-style additive shape if full replacement would break too much at once.
- Keep the parser tolerant when sections are missing, but do not silently invent empty evidence.
- Preserve `idea_id`, `angle_id`, and a research stop/explanation field.

Acceptance criteria:
- The parser can build a valid `ResearchPack` with typed evidence records from prompt output.
- The prompt docstring and `CONTENT_GEN_STAGE_CONTRACTS` stay aligned with the parser behavior.
- Existing callers can still detect whether research is thin or degraded.

Validation:
- Add or update parser tests for complete output and partial output.

Out of scope:
- Search query expansion
- Orchestrator stage wiring

