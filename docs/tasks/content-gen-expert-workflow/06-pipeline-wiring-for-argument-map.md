# Task 06: Insert Argument Map Into The Pipeline

Status: Done

Goal:
Wire the new argument-map stage into the content pipeline and stage tracing.

Primary files:
- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/orchestrator.py`
- `src/cc_deep_research/content_gen/router.py`

Scope:
- Add `argument_map` to `PipelineContext`.
- Insert a new stage between `build_research_pack` and `run_scripting`.
- Update `PIPELINE_STAGES`, labels, prerequisites, stage summaries, metadata, and handler tables.
- Add the agent factory entry in the orchestrator.
- Ensure router progress and serialized context still work with the new stage.

Implementation notes:
- Keep stage numbering internally consistent everywhere it appears.
- Update trace metadata so the dashboard can expose proof-anchor counts or similar useful information.
- Avoid breaking existing resume logic more than necessary.

Acceptance criteria:
- The full pipeline can execute through the new stage.
- Stage traces include the new stage with sensible summaries and metadata.
- `PipelineContext.model_dump_json()` still works end to end.

Validation:
- Add or update orchestrator tests that assert stage count and sequencing.

Out of scope:
- Scripting changes that consume the argument map
- Dashboard UI work
