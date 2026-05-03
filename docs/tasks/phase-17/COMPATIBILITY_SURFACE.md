# Compatibility Surface Audit: ContentGenOrchestrator

## Background

`legacy_orchestrator.py` (~4131 lines, ~36k tokens) contains the deprecated `ContentGenOrchestrator` class. Normal execution routes through `ContentGenPipeline` and `ScriptingRunService`. This audit identifies what must remain as compatibility wrappers vs. legacy internals that can be deleted.

## Compatibility Map

### A. Public Compatibility API (must remain as deprecated wrappers)

These are called by tests, API routes, or downstream code and cannot be deleted:

| Method | Location | Notes |
|--------|----------|-------|
| `establish_brief_reference()` | `orchestrator.py` facade | Wraps `BriefService` + snapshot creation |
| `_build_brief_snapshot()` | Called by `establish_brief_reference` | Brief snapshot builder |
| `get_brief_for_run()` | `test_content_gen_briefs.py` | Managed brief entry point |
| `_load_brief_revision_content()` | Called by `get_brief_for_run` | Revision content loading |
| `get_brief_revisions_info()` | `test_content_gen_briefs.py` | Revision info |
| `create_seeded_run_reference()` | `test_content_gen_briefs.py` | Seeded run reference |
| `create_clone_reference()` | `test_content_gen_briefs.py` | Clone reference |
| `run_full_pipeline()` | Used by API | Main pipeline entry; must delegate to `ContentGenPipeline` |
| `run_scripting()` | `test_content_gen_briefs.py` | Single-pass scripting |
| `run_scripting_from_step()` | `test_content_gen_briefs.py` | Resume scripting |
| `run_scripting_iterative()` | `test_content_gen_briefs.py` | Iterative scripting loop |
| `_extract_retrieval_gaps()` | `test_iterative_loop.py` | Static helper |
| `_build_targeted_feedback()` | `test_iterative_loop.py` | Static helper |
| `_should_use_targeted_mode()` | `test_iterative_loop.py` | Static helper |
| `_apply_targeted_feedback()` | `test_iterative_loop.py` | Static helper (calls other statics) |

### B. Test-Only Legacy Helpers (should move to dedicated modules)

| Method | Used By | Action |
|--------|---------|--------|
| `run_backlog`, `run_scoring`, `run_angle`, etc. | None (dead code) | Delete after T4/T5 |
| `_summarize_input`, `_summarize_output` | Only `_run_stage` | Delete after T5 |

### C. Legacy Internals (delete after extraction + delegation)

- `_PIPELINE_HANDLERS` list
- All `_stage_*` module-level functions
- `_run_stage`, `_run_iterative_loop`, `_run_targeted_revision`, `_evaluate_quality`
- Lane/candidate resolution helpers: `_active_candidate_ids`, `_lane_candidates`, `_resolve_lane_context`, `_resolve_lane_angle`, `_resolve_selected_idea_id`, `_resolve_selected_item`, `_ensure_lane_context`
- Other helpers: `_parse_timestamp_with_tz`, `_update_candidate_status`, `_sync_primary_lane`, `_record_lane_completion`, `_lane_publish_prereqs_met`, `_upsert_progressive_issue`, `_record_progressive_checkpoint`, `_evaluate_fact_risk_gate`, `_build_run_metrics`, `_seed_structure_from_argument_map`, `_seed_beat_intents_from_argument_map`, `_compute_research_depth_routing`, `_thesis_to_angle_option_like`, `_get_content_type_profile`, `_use_combined_execution_brief`, `_build_trace_metadata`, `_collect_trace_warnings`, `_build_decision_summary`, `_format_research_context`, `_format_qc_research_summary`, `_format_qc_argument_map_summary`, `_build_claim_ledger`, `_build_combined_execution_brief`
- `validate_resume_context` (duplicate definition at line ~994 and ~1504)

### D. Module-Level Helpers Only Used by Stage Handlers

These helpers only appear in `_stage_*` functions and are deleted when stage handlers are removed:

```
_PIPELINE_HANDLERS (line 4064)
_stage_load_strategy (line 2719)
_stage_plan_opportunity (line 2729)
_stage_build_backlog (line 2778)
_stage_score_ideas (line 2798)
_stage_generate_angles (line 2842)
_stage_build_research_pack (line 2868)
_stage_build_argument_map (line 2931)
_stage_run_scripting (line 3028)
_stage_visual_translation (line 3358)
_stage_production_brief (line 3384)
_stage_combined_execution_brief (line 3448)
_stage_packaging (line 3657)
_stage_human_qc (line 3704)
_stage_publish_queue (line 3815)
_stage_performance (line 4018)
```

### E. Brief Service / Gate Policy

These methods must survive because they're called by `ContentGenPipeline` via policy objects:

| Method | Notes |
|--------|-------|
| `initialize_brief_gate()` | Returns `BriefExecutionGate`; used in brief lifecycle |
| `check_stage_gate()` | Gate checking logic |
| `get_gate_status_message()` | Gate status formatting |
| `_get_default_gate_policy()` | Policy helper |

### F. Token Size Target

After all extraction + cleanup:
- `legacy_orchestrator.py` target: < 5k `o200k_base` tokens
- Current size: ~36k tokens
- Savings needed: ~31k tokens (~85% reduction)

## Verification

After implementing T2-T5, verify:
1. `rg "legacy_orchestrator" src tests docs` shows only compatibility imports/docs/regression references
2. `legacy_orchestrator.py` is < 5k tokens
3. All tests in `tests/test_content_gen_*.py` pass
4. `uv run ruff check src/ tests/` and `uv run mypy src/` pass
