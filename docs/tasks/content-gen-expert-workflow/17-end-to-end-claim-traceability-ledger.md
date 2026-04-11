# Task 17: Add End-To-End Claim Traceability Ledger

Status: Done

Goal:
Make every major script claim explicitly traceable from final output back through beat planning, argument-map support, research claims, proof anchors, and source identifiers.

Primary files:
- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/agents/scripting.py`
- `src/cc_deep_research/content_gen/agents/qc.py`
- `src/cc_deep_research/content_gen/orchestrator.py`

Scope:
- Add a structured claim-traceability ledger to the workflow models.
- Record mappings between research claims, argument-map claims, beat claims, and final-script supported statements.
- Detect and surface claims that were introduced late without support, dropped without explanation, or weakened during revision.
- Expose traceability summaries through stage traces and QC inputs so operators can see where support breaks down.

Implementation notes:
- Reuse existing claim and proof ids where possible instead of creating a parallel identifier system.
- Prefer additive trace structures over rewriting the current scripting models from scratch.
- Keep the ledger machine-readable first; lightweight human-readable summaries can be derived from it later.

Acceptance criteria:
- The pipeline can answer "where did this claim come from?" for major script assertions.
- QC and evaluator flows can flag unsupported newly introduced claims using trace data rather than prompt heuristics alone.
- Traceability data survives serialization and resume through `PipelineContext`.

Validation:
- Add tests for claim lineage mapping across research, argument map, scripting, and QC.
- Add a regression test where a newly introduced unsupported claim is detectable via the ledger.

Out of scope:
- Automatic inline citations in the final script
- Dashboard visualization redesign

## Implementation Summary

Added the following new models to `models.py`:
- `ClaimTraceStatus` - StrEnum tracking claim status (SUPPORTED, UNSUPPORTED, WEAKENED, INTRODUCED_LATE, DROPPED, UNKNOWN)
- `ClaimTraceStage` - StrEnum tracking where claim first appeared (RESEARCH_PACK, ARGUMENT_MAP, BEAT_PLAN, SCRIPTING)
- `ScriptClaimStatement` - A claim made in the final script with traceability info
- `ClaimTraceEntry` - Single claim's lineage entry in the traceability ledger
- `ClaimTraceLedger` - Collection of trace entries with methods to query lineage

Updated models:
- `ScriptingContext` - Added `claim_ledger: ClaimTraceLedger | None` field
- `PipelineContext` - Added `claim_ledger: ClaimTraceLedger | None` field

Updated `orchestrator.py`:
- Added `_build_claim_ledger()` function to build traceability ledger from research pack, argument map, and scripting context
- Modified `_stage_run_scripting()` to build claim ledger after scripting completes
- Modified `_stage_human_qc()` to pass claim traceability summary to QC agent

Added 10 new tests in `tests/test_content_gen.py`:
- `test_claim_ledger_initialized_from_research_pack`
- `test_claim_ledger_tracks_argument_map_claims`
- `test_claim_ledger_detects_introduced_late_claim`
- `test_claim_ledger_detects_dropped_claim`
- `test_claim_ledger_script_claim_statement_tracking`
- `test_claim_ledger_unsupported_script_claim_detection`
- `test_claim_ledger_claims_needing_attention`
- `test_claim_ledger_to_summary`
- `test_claim_ledger_unsupported_claims_for_qc`
- `test_claim_ledger_pipeline_context_serialization`
- `test_script_claim_statement_model`
