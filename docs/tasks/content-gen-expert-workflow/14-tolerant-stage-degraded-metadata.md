# Task 14: Enrich Degraded Metadata For Tolerant Stages

Status: Planned

Goal:
Make tolerant stages fail more transparently by recording why output was partial, degraded, or empty instead of collapsing everything into sparse models.

Primary files:
- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/orchestrator.py`
- `src/cc_deep_research/content_gen/agents/backlog.py`
- `src/cc_deep_research/content_gen/agents/research_pack.py`
- `src/cc_deep_research/content_gen/agents/production.py`
- `src/cc_deep_research/content_gen/agents/publish.py`
- `src/cc_deep_research/content_gen/agents/performance.py`

Scope:
- Define richer degraded-state fields for tolerant stages.
- Distinguish at least these cases:
  - blank LLM response after retry
  - parser produced zero usable records
  - parser produced partial usable records
  - upstream dependency was incomplete but execution continued
- Surface degraded details through stage traces so CLI and dashboard operators can see what happened.

Implementation notes:
- Keep fail-fast stages fail-fast.
- Prefer structured metadata fields over burying details in `decision_summary` prose.
- Avoid a giant generic error blob; stage-specific reasons should stay legible.

Acceptance criteria:
- Tolerant stage outputs can describe whether they were complete, partial, or effectively empty.
- Stage traces expose enough structured data for the UI to distinguish degraded outcomes.
- Existing successful paths stay backward-compatible and do not become noisier.

Validation:
- Add unit tests for degraded metadata on tolerant agents.
- Add orchestrator trace tests that verify degraded information survives into `PipelineContext.stage_traces`.

Out of scope:
- Dashboard redesign
- Converting tolerant stages to fail-fast behavior
