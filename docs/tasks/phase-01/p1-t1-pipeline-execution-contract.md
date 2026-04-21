# Pipeline Execution Contract

**Version:** 1.0
**Contract Version:** 1.8.0 (aligned with `ContentGenStageContract`)
**Last Updated:** 2026-04-21
**Status:** Proposed — to be confirmed against all callers before P1-T2 implementation.

---

## Overview

`ContentGenPipeline` is the primary pipeline coordinator for the content generation workflow. It sequences 14 stages (0–13) via dedicated stage orchestrators, handles prerequisites and gate checks, emits traces, and supports resume, cancellation, and progress callbacks.

`ContentGenOrchestrator` (in `legacy_orchestrator.py`) is the legacy entry point that wraps the pipeline and adds the iterative quality loop, managed brief handoff, and telemetry persistence. It MUST remain backward-compatible with all existing callers.

---

## Public Entry Points

### `ContentGenPipeline(config: Config)`

The main pipeline coordinator. Does not hold long-lived state; all mutable state lives in `PipelineContext`.

#### Constructor Dependencies
- `config: Config` — injected; used to construct stage orchestrators and services.

#### Internal Dependencies (created on demand)
The following are created lazily inside stage orchestrators. Tests may mock these via the `config` fixture or by patching stage orchestrator methods:

| Dependency | How Injected | Mock Point |
|---|---|---|
| Stage orchestrators (e.g., `BacklogStageOrchestrator`) | Created by `_create_stage()` using `self._config` | Patch `ContentGenPipeline._get_stage()` or individual `run_*` methods |
| LLM agents (e.g., `BacklogAgent`) | Created lazily inside stage orchestrator via `_create_agent()` | Patch stage orchestrator's `_get_agent()` or `_create_agent()` |
| Stores (e.g., `StrategyStore`, `BacklogService`) | Created on-demand inside stage methods | Patch at the stage orchestrator method level |

---

### Primary Method: `run_stage()`

```python
async def run_stage(
    self,
    stage_index: int,
    ctx: PipelineContext,
    progress_callback: Callable[[int, str], None] | None = None,
    stage_completed_callback: Callable[[int, str, str, PipelineContext], None] | None = None,
) -> PipelineContext
```

Runs a single stage by index. Returns the mutated `ctx`.

#### Parameters

| Parameter | Type | Description |
|---|---|---|
| `stage_index` | `int` | 0-based stage index (0–13). Out-of-range raises `ValueError`. |
| `ctx` | `PipelineContext` | Mutable pipeline state. Passed by reference; mutated in place. |
| `progress_callback` | `Callable[[int, str], None] \| None` | Called at stage start with `(stage_index, stage_label)`. Optional. |
| `stage_completed_callback` | `Callable[[int, str, str, PipelineContext], None] \| None` | Called on completion/skipped/fail/blocked. Signature: `(stage_index, status, detail, ctx)`. Optional. |

#### Status Values for `stage_completed_callback`

| Status | Meaning |
|---|---|
| `"completed"` | Stage ran and produced output. |
| `"skipped"` | Prerequisites not met; stage was skipped. |
| `"blocked"` | Brief gate blocked execution. `detail` contains error message. |
| `"failed"` | Stage raised an exception. `detail` contains exception message. |

#### Stage Index to Label Mapping

```python
PIPELINE_STAGES = [
    "load_strategy",       # 0
    "plan_opportunity",    # 1
    "build_backlog",       # 2
    "score_ideas",         # 3
    "generate_angles",      # 4
    "build_research_pack", # 5
    "build_argument_map",  # 6
    "run_scripting",       # 7
    "visual_translation",  # 8
    "production_brief",    # 9
    "packaging",           # 10
    "human_qc",            # 11
    "publish_queue",       # 12
    "performance_analysis",# 13
]
```

#### Stage Gate Behavior

- **Prerequisites check** — Runs before every stage. If unmet, stage is skipped and a trace is appended.
- **Brief gate check** — Runs after prerequisites. If gate blocks, raises `RuntimeError`.
- Neither block raises if the stage is out of range for the current pipeline run (i.e., `run_stage` itself doesn't validate range — callers are responsible).

#### Trace Behavior

Every call to `run_stage()` appends exactly one `PipelineStageTrace` to `ctx.stage_traces` with:
- `stage_index`, `stage_name`, `stage_label`
- `phase` and `phase_label` (from `get_phase_for_stage()`)
- `policy` (from `get_phase_policy()`)
- `status`: `"completed"`, `"skipped"`, `"blocked"`, or `"failed"`
- `started_at`, `completed_at`, `duration_ms`
- `input_summary` / `output_summary` (stage-specific strings)
- `warnings` list (may be empty)
- `decision_summary` string
- `metadata: StageTraceMetadata` (stage-specific metrics)

---

### Secondary Methods (Standalone Stage Execution)

These delegate directly to stage orchestrators. They are used for testing and ad-hoc execution:

```python
async def run_backlog(self, theme: str, *, count: int = 20) -> Any
async def run_scoring(self, items: list) -> Any
async def run_angle(self, item: Any) -> Any
async def run_research(self, item: Any, angle: Any) -> Any
async def run_argument_map(self, item: Any, angle: Any, research_pack: Any) -> Any
async def run_scripting(self, idea: Any, **kwargs: Any) -> Any
async def run_visual(self, scripting_ctx: Any, **kwargs: Any) -> Any
async def run_production(self, visual_plan: Any) -> Any
async def run_packaging(self, script: Any, angle: Any, **kwargs: Any) -> Any
async def run_qc(self, script: str, **kwargs: Any) -> Any
async def run_publish(self, packaging: Any, **kwargs: Any) -> Any
```

**Note:** These do NOT update `ctx.stage_traces`. They return raw stage outputs.

---

## PipelineContext

`PipelineContext` is the central data object. It is a Pydantic `BaseModel`; always passed by reference. For resume, callers MUST pass a **deep-copied** context:

```python
ctx = initial_context.model_copy(deep=True)
```

Using the original context directly (without copy) may cause aliasing bugs.

### Key Fields

| Field | Type | Description |
|---|---|---|
| `pipeline_id` | `str` | Auto-generated 12-char hex. Can be overridden. |
| `theme` | `str` | The content theme/topic. |
| `current_stage` | `int` | Set by `run_stage()` before running each stage. |
| `run_constraints` | `RunConstraints \| None` | Per-run overrides (content type, effort tier, owner, channel goal, success target, iteration settings). |
| `opportunity_brief` | `OpportunityBrief \| None` | The brief for the current run. May be injected externally or produced by stage 1. |
| `brief_reference` | `PipelineBriefReference \| None` | Managed brief reference (brief ID + lifecycle state). |
| `brief_gate` | `BriefExecutionGate \| None` | Gate policy for the run. Initialized by `ContentGenOrchestrator` when using managed briefs. |
| `strategy` | `StrategyMemory \| None` | Strategy context loaded at stage 0. |
| `backlog` | `BacklogOutput \| None` | Output of stage 2 (build_backlog). |
| `scoring` | `ScoringOutput \| None` | Output of stage 3 (score_ideas). |
| `shortlist` | `list[str]` | Shortlisted idea IDs. |
| `selected_idea_id` | `str` | Primary selected idea. |
| `active_candidates` | `list[PipelineCandidate]` | Candidates being processed in current phase. |
| `lane_contexts` | `list[PipelineLaneContext]` | Per-idea lane state for multi-lane runs. |
| `thesis_artifact` | `ThesisArtifact \| None` | Output of angle stage for primary lane. |
| `angles` | `AngleOutput \| None` | Output of stage 4 (generate_angles). |
| `research_pack` | `ResearchPack \| None` | Output of stage 5 (build_research_pack). |
| `argument_map` | `ArgumentMap \| None` | Output of stage 6 (build_argument_map). |
| `scripting` | `ScriptingContext \| None` | Output of stage 7 (run_scripting). |
| `visual_plan` | `VisualPlanOutput \| None` | Output of stage 8 (visual_translation). |
| `production_brief` | `ProductionBrief \| None` | Output of stage 9 (production_brief). |
| `execution_brief` | `VisualProductionExecutionBrief \| None` | Combined brief for visual production. |
| `packaging` | `PackagingOutput \| None` | Output of stage 10 (packaging). |
| `qc_gate` | `HumanQCGate \| None` | Output of stage 11 (human_qc). |
| `publish_items` | `list[PublishItem]` | Output of stage 12 (publish_queue). |
| `publish_item` | `PublishItem \| None` | First publish item (convenience accessor). |
| `performance` | `PerformanceAnalysis \| None` | Output of stage 13 (performance_analysis). |
| `stage_traces` | `list[PipelineStageTrace]` | Accumulated stage execution traces. |
| `claim_ledger` | `ClaimTraceLedger \| None` | Claim tracing for fact-checking. |
| `iteration_state` | `IterationState \| None` | Iteration counter and state. |

---

## RunConstraints

```python
class RunConstraints(BaseModel):
    content_type: str = ""           # e.g., "video_essay", "short_form"
    effort_tier: EffortTier = EffortTier.STANDARD
    owner: str = ""
    channel_goal: str = ""
    success_target: str = ""
    target_platforms: list[str] = []
    use_iterative_loop: bool = True   # enables iterative quality loop
    max_iterations: int | None = None # overrides config default
    research_depth_override: Literal["", "light", "standard", "deep"] = ""
    research_override_reason: str = ""
```

If `run_constraints` is not provided at pipeline start, a default `RunConstraints()` is created.

---

## Resume Behavior

**Requirement:** Caller must deep-copy the context before passing as `initial_context`.

```python
# Correct
ctx = original_context.model_copy(deep=True)
result = await pipeline.run_stage(5, ctx, ...)

# Wrong — aliasing risk
result = await pipeline.run_stage(5, original_context, ...)
```

`ContentGenOrchestrator.run_full_pipeline()` handles this correctly:
```python
ctx = initial_context.model_copy(deep=True) if initial_context else ...
```

**Validation:** `ContentGenOrchestrator.validate_resume_context()` checks prerequisite availability before allowing resume. `ContentGenPipeline` itself does not validate prerequisites for resume — that is the caller's responsibility.

**Seeded context behavior:** When `initial_context` is provided with partial output (e.g., only stages 0–4 completed), `run_stage()` will skip stages whose prerequisites are unmet. See prerequisite table below.

---

## Cancellation Behavior

Cancellation is coordinated through `PipelineRunJob.cancel_requested` (a `threading.Event`) in `progress.py`. The flag exists on the job object, not on `PipelineContext` or `ContentGenPipeline`.

**Propagation path:**
1. Caller sets `job.cancel_requested.set()`
2. At next progress callback check (in the route loop), `job.stop_requested` returns `True`
3. Caller raises `RuntimeError(f"Pipeline {job.pipeline_id} was cancelled")`

**Stage-level cancellation:** Stage orchestrators do NOT currently check `cancel_requested` mid-execution. Long-running LLM calls cannot be interrupted by cancellation alone — the caller must rely on the progress callback check between stages.

This means cancellation is cooperative but not preemptive within stages.

---

## Progress Callback

`progress_callback(stage_index: int, label: str)` is called:
- Once at the start of each `run_stage()` call, before prerequisite/gate checks
- During iterative loop iteration transitions: `progress_callback(-1, f"Iteration {n}/{max}")`

The callback is the cancellation check point in the router loop.

---

## Stage Prerequisites

| Stage Index | Stage Name | Prerequisites |
|---|---|---|
| 0 | `load_strategy` | None (always runs) |
| 1 | `plan_opportunity` | None (always runs) |
| 2 | `build_backlog` | None (always runs) |
| 3 | `score_ideas` | `ctx.backlog is not None` |
| 4 | `generate_angles` | `ctx.backlog is not None` AND at least one lane candidate has a backlog item |
| 5 | `build_research_pack` | `ctx.backlog is not None` AND each active candidate has both backlog item AND angle |
| 6 | `build_argument_map` | Each active candidate has `research_pack`, backlog item, and angle |
| 7 | `run_scripting` | Each active candidate has `argument_map`, approved `fact_risk_gate`, backlog item, and angle |
| 8 | `visual_translation` | `ctx.scripting is not None` |
| 9 | `production_brief` | `ctx.visual_plan is not None` |
| 10 | `packaging` | `ctx.production_brief is not None` or `ctx.execution_brief is not None` |
| 11 | `human_qc` | `ctx.packaging is not None` |
| 12 | `publish_queue` | At least one lane has approved QC |
| 13 | `performance_analysis` | `ctx.publish_items` is not empty |

If prerequisites are not met, the stage is **skipped** (not failed) and a trace is recorded with `status="skipped"`.

---

## Brief Gate

`BriefExecutionGate` is initialized by `ContentGenOrchestrator` when a managed brief reference is established. It is NOT initialized for inline/unmanaged runs.

Gate policies:
- `PERMISSIVE` — always allows progression
- `GATED` — requires brief to be in appropriate lifecycle state
- `STRICT` — raises on any gate block

When gate blocks: `RuntimeError` is raised with the gate message. The stage trace records `status="blocked"`.

---

## Known Compatibility Requirements

### Caller: `radar/router.py`

The radar router calls `ContentGenOrchestrator.run_full_pipeline()` with these known parameters:
- `theme`, `from_stage=0`, `to_stage=end`, `progress_callback`, `stage_completed_callback`
- Creates a `PipelineRunJob` and checks `job.stop_requested` in the progress callback to detect cancellation.

**Contract must support:** `progress_callback` that raises `RuntimeError` on cancellation, `stage_completed_callback` for job status updates.

### Caller: `tests/test_radar_api.py`

Mocks `ContentGenOrchestrator` entirely via `monkeypatch.setattr` on the class. Does not instantiate the real pipeline.

**Contract must support:** Mocking the entire orchestrator class without instantiating LLM agents.

### Caller: `tests/test_iterative_loop.py`

Imports `ContentGenOrchestrator` and calls `._extract_retrieval_gaps()` and `._build_targeted_feedback()` as static helpers. These are internal helpers, not part of the public contract.

**Contract note:** These internal helpers are used by tests but are not part of the public execution contract. They may be refactored.

### Caller: `tests/test_content_gen_briefs.py`

Uses `BriefService`, `BriefRevisionStore`, `SqliteBriefStore`, and brief models. Does not call the pipeline directly.

**Contract note:** Brief service is orthogonal to the pipeline execution contract.

---

## Dependencies: Injected vs. Mocked vs. Internal

| What | How Handled |
|---|---|
| `Config` | Injected into `ContentGenPipeline` constructor |
| Stage orchestrators | Created lazily from `Config` inside `ContentGenPipeline._create_stage()` |
| LLM agents | Created lazily inside stage orchestrators |
| Stores (StrategyStore, BacklogService, etc.) | Created on-demand inside stage methods |
| Brief service | Created inside `ContentGenOrchestrator` via `_get_brief_service()` |

**For tests without real LLM calls:**
- Mock `progress_callback` to raise on cancellation
- Mock `stage_completed_callback` to capture state
- Use `run_backlog()`, `run_angle()`, etc. on stage orchestrators directly for unit-level isolation
- Mock at the agent level by patching `_get_agent()` on stage orchestrators

---

## What Is NOT Part of the Contract

The following are internal to `ContentGenOrchestrator` and are NOT part of the `ContentGenPipeline` public execution contract:

1. **Iterative loop** — `ContentGenPipeline` does not implement the iterative quality loop. That is the responsibility of `ContentGenOrchestrator`.
2. **Telemetry persistence** — `ContentGenPipeline` does not write telemetry. `ContentGenOrchestrator` calls `_persist_run_metrics()` after pipeline completion.
3. **Managed brief lifecycle** — `BriefService` and `BriefRevisionStore` are owned by `ContentGenOrchestrator`.
4. **`_extract_retrieval_gaps()` and `_build_targeted_feedback()`** — These are internal helpers on `ContentGenOrchestrator`, not public.

---

## Verification Checklist

Before marking this contract complete, confirm:

- [ ] All callers of `ContentGenOrchestrator` are reviewed and their parameter usage matches the contract
- [ ] `run_stage()` signature supports all known caller patterns (progress_callback, stage_completed_callback)
- [ ] Resume with deep-copy is enforced in all documented resume paths
- [ ] Cancellation propagation path is documented and cooperative (not preemptive)
- [ ] Brief gate behavior for unmanaged runs is explicitly documented as no-op
- [ ] Stage orchestrators that are not yet implemented (0, 1, 13) are called out as NOP/placeholder
- [ ] Test mocking strategy is documented for the three known test files