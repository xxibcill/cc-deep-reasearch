"""FastAPI router for content generation pipeline endpoints."""

from __future__ import annotations

import json
import logging
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError, model_validator

from cc_deep_research.config import load_config
from cc_deep_research.content_gen.agents.backlog_chat import (
    BacklogChatAgent,
    apply_operations,
    build_apply_operations,
)
from cc_deep_research.content_gen.agents.backlog_triage import (
    BatchTriageAgent,
    apply_triage_operations,
)
from cc_deep_research.content_gen.agents.backlog_triage import (
    build_apply_operations as build_triage_apply_operations,
)
from cc_deep_research.content_gen.agents.execution_brief import ExecutionBriefAgent
from cc_deep_research.content_gen.agents.next_action import NextActionAgent
from cc_deep_research.content_gen.backlog_service import BacklogService
from cc_deep_research.content_gen.maintenance_workflow import (
    MaintenanceJobType,
    MaintenanceProposalStatus,
    MaintenanceScheduler,
    MaintenanceStore,
)
from cc_deep_research.content_gen.models import (
    BacklogItem,
    HookSet,
    ReleaseState,
    RunConstraints,
    ScriptingContext,
    ScriptingIterations,
    ScriptingIterationSummary,
    ScriptingRunResult,
)
from cc_deep_research.content_gen.progress import PipelineRunJobRegistry
from cc_deep_research.content_gen.storage import (
    AuditActor,
    AuditEventType,
    AuditStore,
    PublishQueueStore,
    ScriptingStore,
    StrategyStore,
)
from cc_deep_research.event_router import EventRouter, WebSocketConnection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class StartPipelineRequest(BaseModel):
    """Request body for starting a pipeline run."""

    theme: str = Field(min_length=1)
    from_stage: int = Field(default=0, ge=0)
    to_stage: int | None = Field(default=None, ge=0)
    content_type: str = ""
    effort_tier: Literal["quick", "standard", "deep"] = "standard"
    owner: str = ""
    channel_goal: str = ""
    success_target: str = ""
    research_depth_override: Literal["", "light", "standard", "deep"] = ""
    research_override_reason: str = ""


class ResumePipelineRequest(BaseModel):
    """Request body for resuming a pipeline run."""

    from_stage: int = Field(default=0, ge=0)


class ApproveQCRequest(BaseModel):
    """Request body for resolving QC with an explicit release state."""

    release_state: Literal["approved", "approved_with_known_risks"] = "approved"
    override_reason: str = ""
    actor: str = "operator"


class ApplyLearningsRequest(BaseModel):
    """Request body for promoting performance learnings into strategy rules."""

    learning_ids: list[str] = Field(default_factory=list)
    operator_approved: bool = True


class RunScriptingRequest(BaseModel):
    """Request body for standalone scripting runs."""

    idea: str = Field(min_length=1)
    iterative_mode: bool | None = None
    max_iterations: int | None = Field(default=None, ge=1, le=5)
    llm_route: Literal["openrouter", "cerebras", "anthropic", "heuristic"] | None = Field(
        default=None
    )


class UpdateStrategyRequest(BaseModel):
    """Request body for updating strategy memory."""

    patch: dict[str, Any] = Field(default_factory=dict)


class UpdateBacklogItemRequest(BaseModel):
    """Request body for updating one backlog item."""

    patch: dict[str, Any] = Field(default_factory=dict)


class CreateBacklogItemRequest(BaseModel):
    """Request body for creating a new backlog item."""

    title: str = ""
    one_line_summary: str = ""
    raw_idea: str = ""
    constraints: str = ""
    idea: str = ""
    category: str = ""
    audience: str = ""
    persona_detail: str = ""
    problem: str = ""
    emotional_driver: str = ""
    urgency_level: str = ""
    source: str = ""
    why_now: str = ""
    hook: str = ""
    content_type: str = ""
    format_duration: str = ""
    key_message: str = ""
    call_to_action: str = ""
    evidence: str = ""
    proof_gap_note: str = ""
    expertise_reason: str = ""
    genericity_risk: str = ""
    risk_level: str = "medium"
    source_theme: str = ""
    selection_reasoning: str = ""

    @model_validator(mode="after")
    def _require_title_or_idea(self) -> CreateBacklogItemRequest:
        if not (self.title or self.idea or self.raw_idea):
            raise ValueError("One of 'title', legacy 'idea', or 'raw_idea' is required")
        return self


class BacklogChatMessage(BaseModel):
    """A single message in the backlog chat conversation."""

    role: Literal["user", "assistant"]
    content: str


class BacklogChatOperationInput(BaseModel):
    """Operation proposed by the chat agent (used in apply request)."""

    kind: Literal["update_item", "create_item"]
    idea_id: str | None = None
    reason: str = ""
    fields: dict[str, Any] = Field(default_factory=dict)


class BacklogChatRespondRequest(BaseModel):
    """Request body for backlog-chat respond endpoint."""

    messages: list[BacklogChatMessage] = Field(default_factory=list)
    backlog_items: list[BacklogItem] = Field(default_factory=list)
    strategy: dict[str, Any] | None = None
    selected_idea_id: str | None = None
    mode: Literal["conversation", "edit"] = "edit"


class BacklogChatApplyRequest(BaseModel):
    """Request body for backlog-chat apply endpoint."""

    operations: list[BacklogChatOperationInput] = Field(default_factory=list)


class TriageOperationInput(BaseModel):
    """Triage operation proposed by the batch triage agent (used in apply request)."""

    kind: Literal[
        "batch_enrich",
        "batch_reframe",
        "dedupe_recommendation",
        "archive_recommendation",
        "priority_recommendation",
    ]
    idea_ids: list[str] = Field(default_factory=list)
    reason: str = ""
    fields: dict[str, Any] = Field(default_factory=dict)
    preferred_idea_id: str | None = None


class TriageRespondRequest(BaseModel):
    """Request body for backlog-ai triage respond endpoint."""

    backlog_items: list[BacklogItem] = Field(default_factory=list)
    strategy: dict[str, Any] | None = None


class TriageApplyRequest(BaseModel):
    """Request body for backlog-ai triage apply endpoint."""

    operations: list[TriageOperationInput] = Field(default_factory=list)


class NextActionRequest(BaseModel):
    """Request body for next-action recommendation endpoint."""

    idea_id: str = Field(min_length=1)
    strategy: dict[str, Any] | None = None


class ExecutionBriefRequest(BaseModel):
    """Request body for execution brief generation endpoint."""

    idea_id: str = Field(min_length=1)
    strategy: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Brief management request / response models
# ---------------------------------------------------------------------------


class CreateBriefRequest(BaseModel):
    """Request body for creating a brief from an OpportunityBrief payload."""

    brief: dict[str, Any] = Field(..., description="OpportunityBrief fields as a dictionary")
    provenance: str = Field(default="generated")
    source_pipeline_id: str = Field(default="")
    revision_notes: str = Field(default="")


class SaveRevisionRequest(BaseModel):
    """Request body for saving a new revision of an existing brief."""

    brief: dict[str, Any] = Field(..., description="OpportunityBrief fields as a dictionary")
    revision_notes: str = Field(default="")
    source_pipeline_id: str = Field(default="")
    expected_updated_at: str | None = Field(
        default=None,
        description="Expected updated_at for optimistic concurrency. If provided and mismatched, returns 409.",
    )


class ApplyRevisionRequest(BaseModel):
    """Request body for applying a revision as the current head."""

    revision_id: str = Field(min_length=1, description="The revision_id to set as current head")
    expected_updated_at: str | None = Field(
        default=None,
        description="Expected updated_at for optimistic concurrency.",
    )


class UpdateBriefRequest(BaseModel):
    """Request body for updating brief metadata (title, etc.)."""

    patch: dict[str, Any] = Field(..., description="Fields to update")
    expected_updated_at: str | None = Field(
        default=None,
        description="Expected updated_at for optimistic concurrency.",
    )


class CloneBriefRequest(BaseModel):
    """Request body for cloning an existing brief."""

    new_title: str | None = Field(default=None, description="Optional new title for the clone")


class BriefAssistantMessage(BaseModel):
    """A single message in the brief assistant conversation."""

    role: Literal["user", "assistant"]
    content: str


class BriefAssistantProposalInput(BaseModel):
    """Proposal from the brief assistant (used in apply request)."""

    reason: str = ""
    fields: dict[str, Any] = Field(default_factory=dict)


class BriefAssistantRespondRequest(BaseModel):
    """Request body for brief-assistant respond endpoint."""

    messages: list[BriefAssistantMessage] = Field(default_factory=list)
    revision_id: str | None = Field(default=None, description="Specific revision to discuss (defaults to current head)")
    mode: Literal["conversation", "edit"] = "edit"


class BriefAssistantApplyRequest(BaseModel):
    """Request body for brief-assistant apply endpoint."""

    proposals: list[BriefAssistantProposalInput] = Field(default_factory=list)
    revision_notes: str = Field(default="", description="Notes about what changed in this revision")


def _build_scripting_iterations(iter_state: Any) -> ScriptingIterations | None:
    if iter_state is None:
        return None
    return ScriptingIterations(
        count=iter_state.current_iteration,
        max_iterations=iter_state.max_iterations,
        converged=iter_state.is_converged,
        quality_history=[
            ScriptingIterationSummary(
                iteration=q.iteration_number,
                score=q.overall_quality_score,
                passes=q.passes_threshold,
            )
            for q in iter_state.quality_history
        ],
    )


def _build_scripting_result(
    ctx: ScriptingContext,
    *,
    run_id: str | None = None,
    execution_mode: Literal["single_pass", "iterative"] = "single_pass",
    iterations: ScriptingIterations | None = None,
) -> ScriptingRunResult:
    script = ScriptingStore.extract_script(ctx)
    return ScriptingRunResult(
        run_id=run_id,
        raw_idea=ctx.raw_idea,
        script=script,
        word_count=len(script.split()) if script else 0,
        context=ctx,
        execution_mode=execution_mode,
        iterations=iterations,
    )


def _serialize_scripting_payload(result: ScriptingRunResult) -> dict[str, Any]:
    payload = result.model_dump(mode="json")
    if payload.get("iterations") is None:
        payload.pop("iterations", None)
    return payload


def _serialize_saved_script_run(run: Any) -> dict[str, Any]:
    payload = run.model_dump(mode="json")
    if payload.get("iterations") is None:
        payload.pop("iterations", None)
    return payload


# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------


def register_content_gen_routes(
    app: FastAPI,
    event_router: EventRouter,
    job_registry: PipelineRunJobRegistry,
) -> None:
    """Register all content-gen API and WebSocket routes on *app*."""
    from cc_deep_research.content_gen.backlog_api_service import (
        BacklogApiService,
        BacklogItemNotFoundError,
        BacklogValidationError,
        DuplicateActivePipelineError,
    )
    from cc_deep_research.content_gen.pipeline_run_service import PipelineRunService

    service = PipelineRunService(job_registry=job_registry, event_router=event_router)
    backlog_api_service = BacklogApiService(backlog_service=None, pipeline_service=service)

    @app.get("/api/content-gen/pipelines")
    async def list_pipelines() -> JSONResponse:
        items = service.list_pipelines()
        return JSONResponse(content={"items": items})

    @app.post("/api/content-gen/pipelines", status_code=202)
    async def start_pipeline(request: StartPipelineRequest) -> JSONResponse:
        run_constraints = RunConstraints(
            content_type=request.content_type,
            effort_tier=request.effort_tier,
            owner=request.owner,
            channel_goal=request.channel_goal,
            success_target=request.success_target,
            research_depth_override=request.research_depth_override,
            research_override_reason=request.research_override_reason,
        )
        result = service.start_pipeline(
            request.theme,
            from_stage=request.from_stage,
            to_stage=request.to_stage,
            run_constraints=run_constraints,
        )
        return JSONResponse(
            status_code=202,
            content={
                "pipeline_id": result.pipeline_id,
                "theme": result.theme,
                "from_stage": result.from_stage,
                "to_stage": result.to_stage,
                "status": result.status,
                "current_stage": result.current_stage,
                "error": result.error,
                "created_at": result.created_at.isoformat(),
                "started_at": result.started_at.isoformat() if result.started_at else None,
                "completed_at": result.completed_at.isoformat() if result.completed_at else None,
            },
        )

    @app.get("/api/content-gen/pipelines/{pipeline_id}")
    async def get_pipeline(pipeline_id: str) -> JSONResponse:
        result = service.get_pipeline_status(pipeline_id)
        if result is None:
            return JSONResponse(status_code=404, content={"error": "Pipeline not found"})
        return JSONResponse(content=result)

    @app.post("/api/content-gen/pipelines/{pipeline_id}/stop")
    async def stop_pipeline(pipeline_id: str) -> JSONResponse:
        from cc_deep_research.content_gen.pipeline_run_service import (
            PipelineNotActiveError,
            PipelineNotFoundError,
        )

        try:
            result = service.stop_pipeline(pipeline_id)
            return JSONResponse(content=result)
        except PipelineNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Pipeline not found"})
        except PipelineNotActiveError:
            return JSONResponse(status_code=409, content={"error": "Pipeline is not active"})

    @app.post("/api/content-gen/pipelines/{pipeline_id}/resume")
    async def resume_pipeline(pipeline_id: str, request: ResumePipelineRequest) -> JSONResponse:
        from cc_deep_research.content_gen.pipeline_run_service import (
            PipelineNotActiveError,
            PipelineNotFoundError,
            ResumeContextError,
        )

        try:
            result = service.resume_pipeline(pipeline_id, from_stage=request.from_stage)
            return JSONResponse(
                content={
                    "pipeline_id": result.pipeline_id,
                    "theme": result.theme,
                    "from_stage": result.from_stage,
                    "to_stage": result.to_stage,
                    "status": result.status,
                    "current_stage": result.current_stage,
                    "error": result.error,
                    "created_at": result.created_at.isoformat(),
                    "started_at": result.started_at.isoformat() if result.started_at else None,
                    "completed_at": result.completed_at.isoformat() if result.completed_at else None,
                },
            )
        except PipelineNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Pipeline not found"})
        except PipelineNotActiveError:
            return JSONResponse(status_code=409, content={"error": "Pipeline is already active"})
        except ResumeContextError as e:
            return JSONResponse(status_code=400, content={"error": str(e)})

    # ------------------------------------------------------------------
    # QC approve
    # ------------------------------------------------------------------

    @app.post("/api/content-gen/qc/{pipeline_id}/approve")
    async def approve_qc(pipeline_id: str, request: ApproveQCRequest) -> JSONResponse:
        job = job_registry.get_job(pipeline_id)
        if job is None:
            return JSONResponse(status_code=404, content={"error": "Pipeline not found"})
        ctx = job.pipeline_context
        if ctx is None or ctx.qc_gate is None:
            return JSONResponse(status_code=400, content={"error": "No QC gate found"})
        ctx.qc_gate.approved_for_publish = True
        if request.release_state == "approved_with_known_risks":
            if not request.override_reason:
                return JSONResponse(
                    status_code=400,
                    content={"error": "override_reason is required for approved_with_known_risks"},
                )
            ctx.qc_gate.release_state = ReleaseState.APPROVED_WITH_KNOWN_RISKS
            ctx.qc_gate.override_actor = request.actor
            ctx.qc_gate.override_reason = request.override_reason
            ctx.qc_gate.override_timestamp = datetime.now(tz=UTC).isoformat()
            try:
                audit = AuditStore(config=load_config())
                audit.log_operator_override(
                    idea_id=ctx.selected_idea_id,
                    original_state="blocked",
                    override_reason=request.override_reason,
                    actor=AuditActor.OPERATOR,
                    actor_label=request.actor,
                    pipeline_id=ctx.pipeline_id,
                    brief_id=ctx.brief_reference.brief_id if ctx.brief_reference else "",
                )
                if ctx.brief_reference:
                    _brief_service().record_override(
                        ctx.brief_reference.brief_id,
                        actor_label=request.actor,
                        reason=request.override_reason,
                        pipeline_id=ctx.pipeline_id,
                    )
            except Exception:
                logger.warning("Failed to persist QC override audit", exc_info=True)
        else:
            ctx.qc_gate.release_state = ReleaseState.APPROVED
            ctx.qc_gate.override_actor = ""
            ctx.qc_gate.override_reason = ""
            ctx.qc_gate.override_timestamp = ""
        job_registry.update_context(pipeline_id, ctx)
        return JSONResponse(
            content={
                "pipeline_id": pipeline_id,
                "approved": True,
                "release_state": ctx.qc_gate.release_state.value,
            }
        )

    # ------------------------------------------------------------------
    # Standalone scripting
    # ------------------------------------------------------------------

    @app.post("/api/content-gen/scripting")
    async def run_scripting(request: RunScriptingRequest) -> JSONResponse:
        config = load_config()
        from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

        orch = ContentGenOrchestrator(config)
        iter_state = None
        iterative_enabled = (
            config.content_gen.enable_iterative_mode
            if request.iterative_mode is None
            else request.iterative_mode
        )
        try:
            if iterative_enabled:
                ctx, iter_state = await orch.run_scripting_iterative(
                    request.idea,
                    llm_route=request.llm_route,
                    max_iterations=request.max_iterations,
                )
            else:
                ctx = await orch.run_scripting(request.idea, llm_route=request.llm_route)
        except Exception as exc:
            logger.exception("Scripting run failed")
            return JSONResponse(status_code=500, content={"error": str(exc)})

        store = ScriptingStore()
        execution_mode: Literal["single_pass", "iterative"] = (
            "iterative" if iter_state is not None else "single_pass"
        )
        iterations = _build_scripting_iterations(iter_state)
        saved = store.save(ctx, execution_mode=execution_mode, iterations=iterations)
        response_content = _build_scripting_result(
            ctx,
            run_id=saved.run_id,
            execution_mode=execution_mode,
            iterations=iterations,
        )
        return JSONResponse(content=_serialize_scripting_payload(response_content))

    # ------------------------------------------------------------------
    # Saved scripts history
    # ------------------------------------------------------------------

    @app.get("/api/content-gen/scripts")
    async def list_scripts() -> JSONResponse:
        store = ScriptingStore()
        runs = store.list_runs(limit=50)
        items = [_serialize_saved_script_run(r) for r in runs]
        return JSONResponse(content={"items": items})

    @app.get("/api/content-gen/scripts/{run_id}")
    async def get_script(run_id: str) -> JSONResponse:
        store = ScriptingStore()
        run = store.get(run_id)
        if run is None:
            return JSONResponse(status_code=404, content={"error": "Script run not found"})
        if run.result_path:
            result_text = ""
            with suppress(Exception):
                from pathlib import Path

                result_text = Path(run.result_path).read_text()
            if result_text:
                return JSONResponse(content=json.loads(result_text))

        script_text = ""
        with suppress(Exception):
            from pathlib import Path

            script_text = Path(run.script_path).read_text()
        context: ScriptingContext | None = None
        with suppress(Exception):
            from pathlib import Path

            context_text = Path(run.context_path).read_text()
            if context_text:
                context = ScriptingContext.model_validate_json(context_text)

        if context is None:
            context = ScriptingContext(raw_idea=run.raw_idea)

        response = _build_scripting_result(
            context,
            run_id=run.run_id,
            execution_mode=run.execution_mode,
            iterations=run.iterations,
        )
        if script_text:
            response.script = script_text
            response.word_count = len(script_text.split())
        return JSONResponse(content=json.loads(response.model_dump_json()))

    # ------------------------------------------------------------------
    # Script variant generation & update
    # ------------------------------------------------------------------

    class GenerateVariantsRequest(BaseModel):
        tone: str | None = None
        cta_goal: str | None = None

    @app.post("/api/content-gen/scripts/{run_id}/generate-variants")
    async def generate_script_variants(
        run_id: str,
        request: GenerateVariantsRequest,
    ) -> JSONResponse:
        """Generate new hook and CTA variants for an existing script run."""
        store = ScriptingStore()
        run = store.get(run_id)
        if run is None:
            return JSONResponse(status_code=404, content={"error": "Script run not found"})

        # Load context
        context: ScriptingContext | None = None
        try:
            from pathlib import Path

            context_text = Path(run.context_path).read_text()
            if context_text:
                context = ScriptingContext.model_validate_json(context_text)
        except (FileNotFoundError, json.JSONDecodeError, ValidationError):
            pass

        if context is None:
            return JSONResponse(
                status_code=400,
                content={"error": "Script context not found - cannot generate variants"},
            )

        # Ensure required fields exist
        if context.core_inputs is None or context.angle is None:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Script is missing core_inputs or angle - run full scripting first"
                },
            )

        # Override tone if provided
        if request.tone is not None:
            context.tone = request.tone
        if request.cta_goal is not None:
            context.cta = request.cta_goal

        # Generate hooks and CTA using ScriptingAgent
        from cc_deep_research.content_gen.agents.scripting import ScriptingAgent
        from cc_deep_research.llm import LLMRouter

        config = load_config()
        llm = LLMRouter(config.content_gen.llm)
        agent = ScriptingAgent(llm)

        # Generate hooks (step 5)
        context = await agent.generate_hooks(context)

        # Generate CTA (step 5b)
        context = await agent.generate_cta(context)

        # Save updated context
        store = ScriptingStore()
        store._save_context(run_id, context)

        return JSONResponse(
            content={
                "hooks": json.loads(context.hooks.model_dump_json()),
                "cta_variants": json.loads(context.cta_variants.model_dump_json()),
            }
        )

    class UpdateScriptRequest(BaseModel):
        hook: str | None = None
        cta: str | None = None
        script: str | None = None

    @app.patch("/api/content-gen/scripts/{run_id}")
    async def update_script(
        run_id: str,
        request: UpdateScriptRequest,
    ) -> JSONResponse:
        """Update a script run with new hook, CTA, or full script content."""
        if request.hook is None and request.cta is None and request.script is None:
            return JSONResponse(
                status_code=400,
                content={"error": "At least one field (hook, cta, or script) must be provided"},
            )

        store = ScriptingStore()
        run = store.get(run_id)
        if run is None:
            return JSONResponse(status_code=404, content={"error": "Script run not found"})

        # Load context
        context: ScriptingContext | None = None
        try:
            from pathlib import Path

            context_text = Path(run.context_path).read_text()
            if context_text:
                context = ScriptingContext.model_validate_json(context_text)
        except (FileNotFoundError, json.JSONDecodeError, ValidationError):
            pass

        if context is None:
            return JSONResponse(
                status_code=400,
                content={"error": "Script context not found"},
            )

        # Update fields
        if request.hook is not None:
            if context.hooks is None:
                context.hooks = HookSet(hooks=[], best_hook=request.hook, best_hook_reason="")
            else:
                context.hooks.best_hook = request.hook

        if request.cta is not None:
            context.cta = request.cta

        if request.script is not None:
            # Update script_path with new script content
            from pathlib import Path

            script_path = Path(run.script_path)
            script_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.write_text(request.script)

        # Save updated context
        store._save_context(run_id, context)

        return JSONResponse(content={"success": True, "run_id": run_id})

    # ------------------------------------------------------------------
    # Backlog
    # ------------------------------------------------------------------

    @app.post("/api/content-gen/backlog")
    async def create_backlog_item(request: CreateBacklogItemRequest) -> JSONResponse:
        try:
            item = backlog_api_service.create_item(request.model_dump())
        except BacklogValidationError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)})
        return JSONResponse(
            content=BacklogApiService.serialize_item(item),
            status_code=201,
        )

    @app.get("/api/content-gen/backlog")
    async def list_backlog() -> JSONResponse:
        return JSONResponse(content=backlog_api_service.serialize_list())

    @app.patch("/api/content-gen/backlog/{idea_id}")
    async def update_backlog_item(idea_id: str, request: UpdateBacklogItemRequest) -> JSONResponse:
        try:
            updated = backlog_api_service.update_item(idea_id, request.patch)
        except BacklogValidationError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)})
        except BacklogItemNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Backlog item not found"})
        return JSONResponse(content=BacklogApiService.serialize_item(updated))

    @app.post("/api/content-gen/backlog/{idea_id}/select")
    async def select_backlog_item(idea_id: str) -> JSONResponse:
        try:
            selected = backlog_api_service.select_item(idea_id)
        except BacklogItemNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Backlog item not found"})
        return JSONResponse(content=BacklogApiService.serialize_item(selected))

    @app.post("/api/content-gen/backlog/{idea_id}/archive")
    async def archive_backlog_item(idea_id: str) -> JSONResponse:
        try:
            archived = backlog_api_service.archive_item(idea_id)
        except BacklogItemNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Backlog item not found"})
        return JSONResponse(content=BacklogApiService.serialize_item(archived))

    @app.delete("/api/content-gen/backlog/{idea_id}")
    async def delete_backlog_item(idea_id: str) -> JSONResponse:
        try:
            backlog_api_service.delete_item(idea_id)
        except BacklogItemNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Backlog item not found"})
        return JSONResponse(content={"removed": 1})

    @app.post("/api/content-gen/backlog/{idea_id}/start", status_code=202)
    async def start_backlog_item(idea_id: str) -> JSONResponse:
        try:
            result = backlog_api_service.start_from_item(idea_id)
        except BacklogItemNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Backlog item not found"})
        except DuplicateActivePipelineError as e:
            return JSONResponse(
                status_code=409,
                content={
                    "error": "Backlog item is already in an active pipeline",
                    "pipeline_id": e.pipeline_id,
                },
            )
        return JSONResponse(
            status_code=202,
            content={
                "pipeline_id": result.pipeline_id,
                "status": result.status,
                "idea_id": idea_id,
                "from_stage": result.from_stage,
                "to_stage": result.to_stage,
            },
        )

    # ------------------------------------------------------------------
    # Brief management
    # ------------------------------------------------------------------

    from cc_deep_research.content_gen.brief_service import BriefService, ConcurrentModificationError
    from cc_deep_research.content_gen.models import (
        BriefLifecycleState,
        BriefProvenance,
        OpportunityBrief,
    )

    def _brief_service() -> BriefService:
        config = load_config()
        service = BriefService(config)
        service.set_audit_store(AuditStore(config=config))
        return service

    @app.get("/api/content-gen/briefs")
    async def list_briefs(
        lifecycle_state: str | None = None,
        limit: int = 50,
    ) -> JSONResponse:
        """List all managed briefs with optional lifecycle state filtering.

        Query params:
        - lifecycle_state: filter by state (draft, approved, superseded, archived)
        - limit: max briefs to return (default 50)
        """
        service = _brief_service()
        output = service.load()
        briefs = output.briefs

        if lifecycle_state:
            try:
                state = BriefLifecycleState(lifecycle_state)
                briefs = [b for b in briefs if b.lifecycle_state == state]
            except ValueError:
                return JSONResponse(status_code=400, content={"error": f"Invalid lifecycle_state: {lifecycle_state}"})

        # Sort by updated_at desc, take limit
        briefs = sorted(briefs, key=lambda b: b.updated_at, reverse=True)[:limit]

        return JSONResponse(content={
            "items": [json.loads(b.model_dump_json()) for b in briefs],
            "count": len(briefs),
        })

    @app.post("/api/content-gen/briefs", status_code=201)
    async def create_brief(request: CreateBriefRequest) -> JSONResponse:
        """Create a new managed brief from an OpportunityBrief payload.

        This creates a new brief resource with a single initial revision.
        The brief starts in DRAFT state.
        """
        service = _brief_service()
        try:
            brief_data = request.brief
            if isinstance(brief_data, dict):
                opportunity = OpportunityBrief.model_validate(brief_data)
            else:
                return JSONResponse(status_code=400, content={"error": "brief must be a dictionary"})

            provenance = BriefProvenance(request.provenance) if request.provenance else BriefProvenance.GENERATED

            managed = service.create_from_opportunity(
                opportunity,
                provenance=provenance,
                source_pipeline_id=request.source_pipeline_id,
                revision_notes=request.revision_notes,
            )
            return JSONResponse(content=json.loads(managed.model_dump_json()))
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)})

    @app.get("/api/content-gen/briefs/{brief_id}")
    async def get_brief(brief_id: str) -> JSONResponse:
        """Get a single brief with its current head revision content."""
        service = _brief_service()
        managed = service.get_brief(brief_id)
        if managed is None:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})

        # Attach current head revision content
        current_revision = service.get_revision(managed.current_revision_id)
        response = json.loads(managed.model_dump_json())
        if current_revision:
            response["current_revision"] = json.loads(current_revision.model_dump_json())

        return JSONResponse(content=response)

    @app.patch("/api/content-gen/briefs/{brief_id}")
    async def update_brief(brief_id: str, request: UpdateBriefRequest) -> JSONResponse:
        """Update brief metadata (title, etc.).

        Note: Use save_revision() to create new content revisions.
        """
        service = _brief_service()
        try:
            updated = service.update_brief(
                brief_id,
                request.patch,
                expected_updated_at=request.expected_updated_at,
            )
        except ConcurrentModificationError as exc:
            return JSONResponse(
                status_code=409,
                content={
                    "error": str(exc),
                    "expected_updated_at": exc.expected_updated_at,
                    "actual_updated_at": exc.actual_updated_at,
                },
            )
        if updated is None:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})
        return JSONResponse(content=json.loads(updated.model_dump_json()))

    @app.get("/api/content-gen/briefs/{brief_id}/revisions")
    async def list_brief_revisions(brief_id: str, limit: int = 50) -> JSONResponse:
        """List all revisions for a brief, most recent first."""
        service = _brief_service()
        revisions = service.list_revisions(brief_id, limit=limit)
        return JSONResponse(content={
            "items": [json.loads(r.model_dump_json()) for r in revisions],
            "count": len(revisions),
        })

    @app.get("/api/content-gen/briefs/{brief_id}/revisions/{revision_id}")
    async def get_brief_revision(brief_id: str, revision_id: str) -> JSONResponse:
        """Get a specific revision by ID."""
        service = _brief_service()
        revision = service.get_revision(revision_id)
        if revision is None or revision.brief_id != brief_id:
            return JSONResponse(status_code=404, content={"error": "Revision not found"})
        return JSONResponse(content=json.loads(revision.model_dump_json()))

    @app.post("/api/content-gen/briefs/{brief_id}/revisions")
    async def save_brief_revision(brief_id: str, request: SaveRevisionRequest) -> JSONResponse:
        """Save a new revision of an existing brief.

        The current_revision_id (head) is NOT changed by this operation.
        Use /apply-revision to promote a revision to head.
        """
        service = _brief_service()
        try:
            brief_data = request.brief
            if isinstance(brief_data, dict):
                opportunity = OpportunityBrief.model_validate(brief_data)
            else:
                return JSONResponse(status_code=400, content={"error": "brief must be a dictionary"})

            revision = service.save_revision(
                brief_id,
                opportunity,
                revision_notes=request.revision_notes,
                source_pipeline_id=request.source_pipeline_id,
                expected_updated_at=request.expected_updated_at,
            )
        except ConcurrentModificationError as exc:
            return JSONResponse(
                status_code=409,
                content={
                    "error": str(exc),
                    "expected_updated_at": exc.expected_updated_at,
                    "actual_updated_at": exc.actual_updated_at,
                },
            )
        if revision is None:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})
        return JSONResponse(content=json.loads(revision.model_dump_json()), status_code=201)

    @app.post("/api/content-gen/briefs/{brief_id}/apply-revision")
    async def apply_revision(brief_id: str, request: ApplyRevisionRequest) -> JSONResponse:
        """Apply a revision as the current head (promote it to active)."""
        service = _brief_service()
        try:
            updated = service.update_head(
                brief_id,
                request.revision_id,
                expected_updated_at=request.expected_updated_at,
            )
        except ConcurrentModificationError as exc:
            return JSONResponse(
                status_code=409,
                content={
                    "error": str(exc),
                    "expected_updated_at": exc.expected_updated_at,
                    "actual_updated_at": exc.actual_updated_at,
                },
            )
        if updated is None:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})
        return JSONResponse(content=json.loads(updated.model_dump_json()))

    @app.post("/api/content-gen/briefs/{brief_id}/approve")
    async def approve_brief(brief_id: str, expected_updated_at: str | None = None) -> JSONResponse:
        """Transition a brief to the approved state."""
        service = _brief_service()
        try:
            updated = service.approve(brief_id, expected_updated_at=expected_updated_at)
        except ConcurrentModificationError as exc:
            return JSONResponse(
                status_code=409,
                content={
                    "error": str(exc),
                    "expected_updated_at": exc.expected_updated_at,
                    "actual_updated_at": exc.actual_updated_at,
                },
            )
        if updated is None:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})
        return JSONResponse(content=json.loads(updated.model_dump_json()))

    @app.post("/api/content-gen/briefs/{brief_id}/archive")
    async def archive_brief(brief_id: str, expected_updated_at: str | None = None) -> JSONResponse:
        """Archive a brief."""
        service = _brief_service()
        try:
            updated = service.archive(brief_id, expected_updated_at=expected_updated_at)
        except ConcurrentModificationError as exc:
            return JSONResponse(
                status_code=409,
                content={
                    "error": str(exc),
                    "expected_updated_at": exc.expected_updated_at,
                    "actual_updated_at": exc.actual_updated_at,
                },
            )
        if updated is None:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})
        return JSONResponse(content=json.loads(updated.model_dump_json()))

    @app.post("/api/content-gen/briefs/{brief_id}/supersede")
    async def supersede_brief(brief_id: str, expected_updated_at: str | None = None) -> JSONResponse:
        """Mark a brief as superseded."""
        service = _brief_service()
        try:
            updated = service.supersede(brief_id, expected_updated_at=expected_updated_at)
        except ConcurrentModificationError as exc:
            return JSONResponse(
                status_code=409,
                content={
                    "error": str(exc),
                    "expected_updated_at": exc.expected_updated_at,
                    "actual_updated_at": exc.actual_updated_at,
                },
            )
        if updated is None:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})
        return JSONResponse(content=json.loads(updated.model_dump_json()))

    @app.post("/api/content-gen/briefs/{brief_id}/revert-to-draft")
    async def revert_brief_to_draft(brief_id: str, expected_updated_at: str | None = None) -> JSONResponse:
        """Revert a brief back to draft state."""
        service = _brief_service()
        try:
            updated = service.revert_to_draft(brief_id, expected_updated_at=expected_updated_at)
        except ConcurrentModificationError as exc:
            return JSONResponse(
                status_code=409,
                content={
                    "error": str(exc),
                    "expected_updated_at": exc.expected_updated_at,
                    "actual_updated_at": exc.actual_updated_at,
                },
            )
        if updated is None:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})
        return JSONResponse(content=json.loads(updated.model_dump_json()))

    @app.post("/api/content-gen/briefs/{brief_id}/clone")
    async def clone_brief(brief_id: str, request: CloneBriefRequest) -> JSONResponse:
        """Clone an existing brief.

        The clone starts with the same current head revision but is otherwise
        independent. Returns the new brief in DRAFT state.
        """
        service = _brief_service()
        cloned = service.clone_brief(brief_id, new_title=request.new_title)
        if cloned is None:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})
        return JSONResponse(content=json.loads(cloned.model_dump_json()), status_code=201)

    @app.get("/api/content-gen/briefs/{brief_id}/audit")
    async def get_brief_audit_history(
        brief_id: str,
        event_type: str | None = None,
        actor: str | None = None,
        limit: int = 100,
    ) -> JSONResponse:
        """Get audit history for a specific brief.

        Query params:
        - event_type: filter by event type (brief_created, brief_updated, etc.)
        - actor: filter by actor (operator, ai_proposal, system, maintenance)
        - limit: max entries to return (default 100)
        """
        store = AuditStore()
        event_type_enum = AuditEventType(event_type) if event_type else None
        actor_enum = AuditActor(actor) if actor else None
        entries = store.load_entries(
            brief_id=brief_id,
            event_type=event_type_enum,
            actor=actor_enum,
            limit=limit,
        )
        return JSONResponse(content={
            "brief_id": brief_id,
            "items": [entry.to_dict() for entry in entries],
            "count": len(entries),
        })

    # ------------------------------------------------------------------
    # Brief Assistant (Phase 05)
    # ------------------------------------------------------------------

    from cc_deep_research.content_gen.agents.brief_assistant import (
        BriefAssistantAgent,
        build_apply_proposals,
    )

    @app.post("/api/content-gen/briefs/{brief_id}/assistant/respond")
    async def brief_assistant_respond(brief_id: str, request: BriefAssistantRespondRequest) -> JSONResponse:
        """Generate a conversational response with optional brief revision proposals.

        This endpoint is advisory only — it never writes to persistent state.
        Use /apply to persist any proposed revisions.
        """
        service = _brief_service()
        managed = service.get_brief(brief_id)
        if managed is None:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})

        # Load the revision to discuss
        revision_id = request.revision_id or managed.current_revision_id
        revision = service.get_revision(revision_id)
        if revision is None or revision.brief_id != brief_id:
            return JSONResponse(status_code=404, content={"error": "Revision not found"})

        agent = BriefAssistantAgent(config=load_config())
        messages = [{"role": m.role, "content": m.content} for m in request.messages]

        response = await agent.respond(
            messages=messages,
            brief_revision=revision,
            mode=request.mode,
        )

        return JSONResponse(content=json.loads(response.model_dump_json()))

    @app.post("/api/content-gen/briefs/{brief_id}/assistant/apply")
    async def brief_assistant_apply(brief_id: str, request: BriefAssistantApplyRequest) -> JSONResponse:
        """Apply a list of validated brief revision proposals.

        This is the only write path for assistant-proposed revisions.
        Returns structured errors instead of crashing on invalid proposals.
        """
        service = _brief_service()
        managed = service.get_brief(brief_id)
        if managed is None:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})

        # Build the opportunity from merged proposals
        current_revision = service.get_revision(managed.current_revision_id)
        if current_revision is None:
            return JSONResponse(status_code=400, content={"error": "No current revision to base changes on"})

        # Start with current revision content
        opportunity_data: dict[str, Any] = {
            "theme": current_revision.theme,
            "goal": current_revision.goal,
            "primary_audience_segment": current_revision.primary_audience_segment,
            "secondary_audience_segments": current_revision.secondary_audience_segments,
            "problem_statements": current_revision.problem_statements,
            "content_objective": current_revision.content_objective,
            "proof_requirements": current_revision.proof_requirements,
            "platform_constraints": current_revision.platform_constraints,
            "risk_constraints": current_revision.risk_constraints,
            "freshness_rationale": current_revision.freshness_rationale,
            "sub_angles": current_revision.sub_angles,
            "research_hypotheses": current_revision.research_hypotheses,
            "success_criteria": current_revision.success_criteria,
            "expert_take": current_revision.expert_take,
            "non_obvious_claims_to_test": current_revision.non_obvious_claims_to_test,
            "genericity_risks": current_revision.genericity_risks,
        }

        # Apply validated proposals
        validated, errors = build_apply_proposals(
            [p.model_dump(mode="python") for p in request.proposals]
        )
        applied_count = 0
        for proposal in validated:
            for key, value in proposal.fields.items():
                if key in opportunity_data:
                    opportunity_data[key] = value
            applied_count += 1

        if applied_count == 0 and errors:
            return JSONResponse(
                status_code=400,
                content={"applied": 0, "errors": errors, "revision": None},
            )

        # Create a new revision with the merged opportunity
        try:
            opportunity = OpportunityBrief.model_validate(opportunity_data)
            revision = service.save_revision(
                brief_id,
                opportunity,
                revision_notes=request.revision_notes or "AI-assisted revision",
                source_pipeline_id="",
            )
        except Exception as exc:
            return JSONResponse(status_code=400, content={"error": str(exc), "applied": 0})

        # Log the assistant origin
        if service._audit_store is not None:
            from cc_deep_research.content_gen.storage import AuditActor, AuditEventType

            service._audit_mutation(
                AuditEventType.BRIEF_REVISION_SAVED,
                brief_id,
                actor=AuditActor.AI_PROPOSAL,
                patch={"revision_id": revision.revision_id, "proposals_count": applied_count},
                brief_snapshot=managed,
                outcome="success",
            )

        return JSONResponse(
            status_code=201,
            content={
                "applied": applied_count,
                "revision": json.loads(revision.model_dump_json()) if revision else None,
                "errors": errors,
            },
        )

    # ------------------------------------------------------------------
    # Brief-to-Backlog Generation (Phase 05 - P5-T2)
    # ------------------------------------------------------------------

    from cc_deep_research.content_gen.agents.brief_to_backlog import (
        generate_backlog_from_brief,
    )

    @app.post("/api/content-gen/briefs/{brief_id}/generate-backlog")
    async def generate_backlog_from_brief_endpoint(
        brief_id: str,
    ) -> JSONResponse:
        """Generate backlog item candidates from an approved brief revision.

        This endpoint is advisory only — it never writes to the backlog.
        Use /apply-backlog to persist any proposed items.
        """
        service = _brief_service()
        managed = service.get_brief(brief_id)
        if managed is None:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})

        # Load the current head revision
        revision = service.get_revision(managed.current_revision_id)
        if revision is None:
            return JSONResponse(status_code=400, content={"error": "No current revision found"})

        result = await generate_backlog_from_brief(revision)

        return JSONResponse(content=json.loads(result.model_dump_json()))

    @app.post("/api/content-gen/briefs/{brief_id}/apply-backlog")
    async def apply_backlog_from_brief(
        brief_id: str,
        items: list[dict[str, Any]],
    ) -> JSONResponse:
        """Apply generated backlog items from a brief to the persistent backlog.

        This persists items to the backlog with trace links back to the brief.
        """
        service = _brief_service()
        managed = service.get_brief(brief_id)
        if managed is None:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})

        revision = service.get_revision(managed.current_revision_id)
        if revision is None:
            return JSONResponse(status_code=400, content={"error": "No current revision found"})

        backlog_service = BacklogService(load_config())
        applied_count = 0
        created_items: list[BacklogItem] = []
        errors: list[str] = []

        for index, item_data in enumerate(items, start=1):
            try:
                if not item_data.get("title") and not item_data.get("idea"):
                    errors.append(f"Item {index}: missing title or idea")
                    continue

                created = backlog_service.create_item(
                    title=str(item_data.get("title", "")),
                    one_line_summary=str(item_data.get("one_line_summary", "")),
                    raw_idea=str(item_data.get("raw_idea", "")),
                    constraints=str(item_data.get("constraints", "")),
                    idea=str(item_data.get("idea", item_data.get("title", ""))),
                    category=str(item_data.get("category", "authority-building")),
                    audience=str(item_data.get("audience", "")),
                    persona_detail=str(item_data.get("persona_detail", "")),
                    problem=str(item_data.get("problem", "")),
                    emotional_driver=str(item_data.get("emotional_driver", "")),
                    urgency_level=str(item_data.get("urgency_level", "medium")),
                    source=str(item_data.get("source", "")),
                    why_now=str(item_data.get("why_now", "")),
                    hook=str(item_data.get("hook", "")),
                    content_type=str(item_data.get("content_type", "")),
                    key_message=str(item_data.get("key_message", "")),
                    call_to_action=str(item_data.get("call_to_action", "")),
                    evidence=str(item_data.get("evidence", "")),
                    risk_level=str(item_data.get("risk_level", "medium")),
                    source_theme=str(item_data.get("source_theme", managed.title or brief_id)),
                    selection_reasoning=str(item_data.get("reason", "")),
                )
                applied_count += 1
                created_items.append(created)

                # Log brief origin on the backlog item
                audit_store = AuditStore(config=load_config())
                audit_store.log_backlog_mutation(
                    event_type=AuditEventType.ITEM_CREATED,
                    idea_id=created.idea_id,
                    actor=AuditActor.OPERATOR,
                    patch={
                        "source_brief_id": brief_id,
                        "source_revision_id": revision.revision_id,
                        "source_revision_version": revision.version,
                        "brief_theme": managed.title,
                    },
                    outcome="success",
                )
            except Exception as exc:
                errors.append(f"Item {index}: {exc}")

        return JSONResponse(
            content={
                "applied": applied_count,
                "items": [json.loads(item.model_dump_json()) for item in created_items],
                "errors": errors,
            },
        )

    # ------------------------------------------------------------------
    # Brief Branching & Sibling Comparison (Phase 05 - P5-T3)
    # ------------------------------------------------------------------

    class BranchBriefRequest(BaseModel):
        """Request body for branching an existing brief."""

        new_title: str | None = Field(default=None, description="Optional new title for the branch")
        branch_reason: str = Field(default="", description="Why this brief is being branched")


    @app.post("/api/content-gen/briefs/{brief_id}/branch")
    async def branch_brief(brief_id: str, request: BranchBriefRequest) -> JSONResponse:
        """Create a branched copy of an existing brief.

        Branch creates a derivative brief that tracks its lineage back to the source.
        Unlike clone (for reuse), branch is for creating variants for different
        themes, channels, or experiments.
        """
        service = _brief_service()
        branched = service.branch_brief(
            brief_id,
            new_title=request.new_title,
            branch_reason=request.branch_reason,
        )
        if branched is None:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})
        return JSONResponse(content=json.loads(branched.model_dump_json()), status_code=201)

    @app.get("/api/content-gen/briefs/{brief_id}/siblings")
    async def list_sibling_briefs(brief_id: str) -> JSONResponse:
        """List briefs that share the same source brief.

        Returns all briefs that were branched from the same source,
        including the source brief itself.
        """
        service = _brief_service()
        managed = service.get_brief(brief_id)
        if managed is None:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})

        siblings = service.list_sibling_briefs(brief_id)

        # Include the source brief itself if this is a branch
        result_briefs = [managed]
        if managed.source_brief_id:
            source = service.get_brief(managed.source_brief_id)
            if source:
                result_briefs = [source] + siblings

        return JSONResponse(content={
            "items": [json.loads(b.model_dump_json()) for b in result_briefs],
            "count": len(result_briefs),
        })

    @app.get("/api/content-gen/briefs/{brief_id}/compare/{other_brief_id}")
    async def compare_briefs(brief_id: str, other_brief_id: str) -> JSONResponse:
        """Compare two briefs side by side.

        Returns both briefs with their current head revisions for comparison.
        """
        service = _brief_service()

        brief_a = service.get_brief(brief_id)
        brief_b = service.get_brief(other_brief_id)

        if brief_a is None or brief_b is None:
            return JSONResponse(status_code=404, content={"error": "One or both briefs not found"})

        revision_a = service.get_revision(brief_a.current_revision_id)
        revision_b = service.get_revision(brief_b.current_revision_id)

        return JSONResponse(content={
            "brief_a": json.loads(brief_a.model_dump_json()),
            "brief_b": json.loads(brief_b.model_dump_json()),
            "revision_a": json.loads(revision_a.model_dump_json()) if revision_a else None,
            "revision_b": json.loads(revision_b.model_dump_json()) if revision_b else None,
        })

    # ------------------------------------------------------------------
    # Backlog chat
    # ------------------------------------------------------------------

    @app.post("/api/content-gen/backlog-chat/respond")
    async def backlog_chat_respond(request: BacklogChatRespondRequest) -> JSONResponse:
        """Generate a conversational response with optional backlog operations.

        This endpoint is advisory only — it never writes to the backlog.
        Use /apply to persist any proposed operations.
        """
        config = load_config()
        service = BacklogService(config)

        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        backlog_items = request.backlog_items if request.backlog_items else service.load().items

        agent = BacklogChatAgent(config)
        response = await agent.respond(
            messages=messages,
            backlog_items=backlog_items,
            strategy=request.strategy,
            selected_idea_id=request.selected_idea_id,
            mode=request.mode,
        )

        return JSONResponse(content=json.loads(response.model_dump_json()))

    @app.post("/api/content-gen/backlog-chat/apply")
    async def backlog_chat_apply(request: BacklogChatApplyRequest) -> JSONResponse:
        """Apply a list of validated backlog operations.

        This is the only write path for chat-proposed operations.
        Returns structured errors instead of crashing on invalid operations.
        """
        config = load_config()
        service = BacklogService(config)

        backlog_items = service.load().items
        operations, errors = build_apply_operations(
            [op.model_dump(mode="python") for op in request.operations],
            backlog_items,
        )
        applied = 0
        items: list[BacklogItem] = []
        if operations:
            applied, items, apply_errors = await apply_operations(operations, service)
            errors.extend(apply_errors)

        return JSONResponse(
            content={
                "applied": applied,
                "items": [json.loads(item.model_dump_json()) for item in items],
                "errors": errors,
            }
        )

    # ------------------------------------------------------------------
    # Backlog AI Triage
    # ------------------------------------------------------------------

    @app.post("/api/content-gen/backlog-ai/triage/respond")
    async def backlog_triage_respond(request: TriageRespondRequest) -> JSONResponse:
        """Generate batch triage proposals for the backlog.

        This endpoint is advisory only — it never writes to the backlog.
        Use /apply to persist any proposed operations.
        """
        config = load_config()
        service = BacklogService(config)

        backlog_items = request.backlog_items if request.backlog_items else service.load().items

        agent = BatchTriageAgent(config)
        response = await agent.respond(
            backlog_items=backlog_items,
            strategy=request.strategy,
        )

        return JSONResponse(content=json.loads(response.model_dump_json()))

    @app.post("/api/content-gen/backlog-ai/triage/apply")
    async def backlog_triage_apply(request: TriageApplyRequest) -> JSONResponse:
        """Apply a list of validated triage operations.

        This is the only write path for triage-proposed operations.
        Returns structured errors instead of crashing on invalid operations.
        """
        config = load_config()
        service = BacklogService(config)

        backlog_items = service.load().items
        operations, errors = build_triage_apply_operations(
            [op.model_dump(mode="python") for op in request.operations],
            backlog_items,
        )
        applied = 0
        items: list[BacklogItem] = []
        if operations:
            applied, items, apply_errors = await apply_triage_operations(operations, service)
            errors.extend(apply_errors)

        return JSONResponse(
            content={
                "applied": applied,
                "items": [json.loads(item.model_dump_json()) for item in items],
                "errors": errors,
            }
        )

    # ------------------------------------------------------------------
    # Next-Action Recommendations
    # ------------------------------------------------------------------

    @app.post("/api/content-gen/backlog-ai/next-action")
    async def get_next_action(request: NextActionRequest) -> JSONResponse:
        """Get a next-action recommendation for a single backlog item.

        This endpoint is advisory only — it never writes to the backlog.
        """
        config = load_config()
        service = BacklogService(config)
        backlog = service.load()

        item = next((i for i in backlog.items if i.idea_id == request.idea_id), None)
        if item is None:
            return JSONResponse(status_code=404, content={"error": "Backlog item not found"})

        agent = NextActionAgent(config)
        response = await agent.recommend(
            item,
            strategy_context=request.strategy,
        )

        return JSONResponse(content=json.loads(response.model_dump_json()))

    @app.post("/api/content-gen/backlog-ai/next-action/batch")
    async def get_next_action_batch(
        request: TriageRespondRequest,
    ) -> JSONResponse:
        """Get next-action recommendations for multiple backlog items.

        Returns recommendations for all items in the request (or all items
        in the backlog if none provided).
        """
        config = load_config()
        service = BacklogService(config)

        backlog_items = request.backlog_items if request.backlog_items else service.load().items

        recommendations = []
        warnings: list[str] = []

        for item in backlog_items:
            agent = NextActionAgent(config)
            try:
                response = await agent.recommend(
                    item,
                    strategy_context=request.strategy,
                )
                recommendations.append(json.loads(response.model_dump_json()))
            except Exception as exc:
                warnings.append(f"{item.idea_id}: {exc}")

        return JSONResponse(content={"recommendations": recommendations, "warnings": warnings})

    # ------------------------------------------------------------------
    # Execution Brief
    # ------------------------------------------------------------------

    @app.post("/api/content-gen/backlog-ai/execution-brief")
    async def generate_execution_brief(request: ExecutionBriefRequest) -> JSONResponse:
        """Generate a production-readiness brief for a single backlog item.

        The brief is grounded in existing backlog metadata and AI-enriched context.
        It helps reduce manual setup work before the pipeline starts.
        """
        config = load_config()
        service = BacklogService(config)
        backlog = service.load()

        item = next((i for i in backlog.items if i.idea_id == request.idea_id), None)
        if item is None:
            return JSONResponse(status_code=404, content={"error": "Backlog item not found"})

        agent = ExecutionBriefAgent(config)
        response = await agent.generate_brief(
            item,
            strategy_context=request.strategy,
        )

        return JSONResponse(content=json.loads(response.model_dump_json()))

    # ------------------------------------------------------------------
    # Strategy
    # ------------------------------------------------------------------

    @app.get("/api/content-gen/strategy")
    async def get_strategy() -> JSONResponse:
        store = StrategyStore()
        memory = store.load()
        return JSONResponse(content=json.loads(memory.model_dump_json()))

    @app.put("/api/content-gen/strategy")
    async def update_strategy(request: UpdateStrategyRequest) -> JSONResponse:
        store = StrategyStore()
        updated = store.update(request.patch)
        return JSONResponse(content=json.loads(updated.model_dump_json()))

    @app.get("/api/content-gen/strategy/readiness")
    async def get_strategy_readiness() -> JSONResponse:
        """Check strategy readiness and return validation results.

        P4-T1: Returns blocking and warning issues so operators can see
        which fields or ratios are causing readiness failures.
        """
        store = StrategyStore()
        result = store.check_readiness()
        return JSONResponse(content=json.loads(result.model_dump_json()))

    @app.get("/api/content-gen/strategy/rules-for-review")
    async def get_rules_for_review() -> JSONResponse:
        """Get all rules that need operator review.

        P4-T2: Returns rules that are under_review, expired, or past their
        review date.
        """
        store = StrategyStore()
        rules = store.get_rules_for_review()
        return JSONResponse(
            content={"items": [json.loads(r.model_dump_json()) for r in rules], "count": len(rules)}
        )

    @app.patch("/api/content-gen/strategy/rule-lifecycle/{version_id}")
    async def update_rule_lifecycle(
        version_id: str,
        status: str | None = None,
        confidence: float | None = None,
        evidence_count: int | None = None,
        review_after: str | None = None,
        review_notes: str | None = None,
    ) -> JSONResponse:
        """Update lifecycle metadata for a rule version.

        P4-T2: Allows operators to promote, deprecate, or schedule review
        for durable rules.
        """
        from cc_deep_research.content_gen.models import RuleLifecycleStatus

        store = StrategyStore()
        normalized_status = RuleLifecycleStatus(status) if status else None
        version = store.update_rule_lifecycle(
            version_id,
            status=normalized_status,
            confidence=confidence,
            evidence_count=evidence_count,
            review_after=review_after,
            review_notes=review_notes,
        )
        if version is None:
            return JSONResponse(
                content={"error": "Rule version not found"},
                status_code=404,
            )
        return JSONResponse(content=json.loads(version.model_dump_json()))

    @app.get("/api/content-gen/learnings")
    async def list_learnings(
        category: str | None = None,
        durability: str | None = None,
    ) -> JSONResponse:
        from cc_deep_research.content_gen.models import LearningCategory, LearningDurability
        from cc_deep_research.content_gen.storage import PerformanceLearningStore

        store = PerformanceLearningStore()
        items = store.get_active_learnings(
            category=LearningCategory(category) if category else None,
            durability=LearningDurability(durability) if durability else None,
        )
        return JSONResponse(
            content={"items": [json.loads(item.model_dump_json()) for item in items], "count": len(items)}
        )

    @app.post("/api/content-gen/learnings/apply")
    async def apply_learnings(request: ApplyLearningsRequest) -> JSONResponse:
        from cc_deep_research.content_gen.storage import PerformanceLearningStore

        store = PerformanceLearningStore()
        guidance = store.apply_learnings_to_strategy(
            request.learning_ids,
            operator_approved=request.operator_approved,
            record_versions=True,
        )
        return JSONResponse(content=json.loads(guidance.model_dump_json()))

    @app.get("/api/content-gen/rule-versions")
    async def list_rule_versions(kind: str | None = None) -> JSONResponse:
        from cc_deep_research.telemetry.query import query_content_gen_rule_versions

        return JSONResponse(content=query_content_gen_rule_versions(kind=kind))

    @app.get("/api/content-gen/operating-fitness")
    async def get_operating_fitness() -> JSONResponse:
        from cc_deep_research.telemetry.query import query_content_gen_operating_fitness

        return JSONResponse(content=query_content_gen_operating_fitness())

    # ------------------------------------------------------------------
    # Publish queue
    # ------------------------------------------------------------------

    @app.get("/api/content-gen/publish")
    async def list_publish_queue() -> JSONResponse:
        store = PublishQueueStore()
        items = store.load()
        return JSONResponse(content={"items": [json.loads(i.model_dump_json()) for i in items]})

    @app.delete("/api/content-gen/publish/{idea_id}/{platform}")
    async def remove_from_queue(idea_id: str, platform: str) -> JSONResponse:
        store = PublishQueueStore()
        items = store.load()
        filtered = [i for i in items if not (i.idea_id == idea_id and i.platform == platform)]
        store.save(filtered)
        removed = len(items) - len(filtered)
        return JSONResponse(content={"removed": removed})

    # ------------------------------------------------------------------
    # Audit history
    # ------------------------------------------------------------------

    @app.get("/api/content-gen/audit")
    async def list_audit_entries(
        idea_id: str | None = None,
        event_type: str | None = None,
        actor: str | None = None,
        limit: int = 100,
    ) -> JSONResponse:
        """List audit log entries with optional filtering.

        Query params:
        - idea_id: filter to entries for a specific backlog item
        - event_type: filter to a specific event type (proposal_created, item_updated, etc.)
        - actor: filter to entries from a specific actor (operator, ai_proposal, system, maintenance)
        - limit: max entries to return (default 100)
        """
        store = AuditStore()
        event_type_enum = AuditEventType(event_type) if event_type else None
        actor_enum = AuditActor(actor) if actor else None
        entries = store.load_entries(
            idea_id=idea_id,
            event_type=event_type_enum,
            actor=actor_enum,
            limit=limit,
        )
        return JSONResponse(
            content={
                "items": [entry.to_dict() for entry in entries],
                "count": len(entries),
            }
        )

    @app.get("/api/content-gen/audit/{idea_id}")
    async def get_audit_for_item(idea_id: str, limit: int = 50) -> JSONResponse:
        """Get audit history for a specific backlog item."""
        store = AuditStore()
        entries = store.load_entries(idea_id=idea_id, limit=limit)
        return JSONResponse(
            content={
                "idea_id": idea_id,
                "items": [entry.to_dict() for entry in entries],
                "count": len(entries),
            }
        )

    # ------------------------------------------------------------------
    # Maintenance workflows
    # ------------------------------------------------------------------

    @app.get("/api/content-gen/maintenance/proposals")
    async def list_maintenance_proposals(
        status: str | None = None,
        job_type: str | None = None,
        limit: int = 50,
    ) -> JSONResponse:
        """List maintenance proposals with optional filtering.

        Query params:
        - status: filter by status (pending, approved, rejected, applied, expired)
        - job_type: filter by job type (stale_item_review, gap_summary, duplicate_watchlist, rescoring_recommend)
        - limit: max proposals to return (default 50)
        """
        store = MaintenanceStore()
        status_enum = MaintenanceProposalStatus(status) if status else None
        job_type_enum = MaintenanceJobType(job_type) if job_type else None
        proposals = store.load_proposals(status=status_enum, job_type=job_type_enum, limit=limit)
        return JSONResponse(
            content={
                "items": [p.to_dict() for p in proposals],
                "count": len(proposals),
            }
        )

    @app.post("/api/content-gen/maintenance/proposals/{proposal_id}/resolve")
    async def resolve_maintenance_proposal(
        proposal_id: str,
        decision: str,  # "approved" | "rejected"
    ) -> JSONResponse:
        """Resolve a maintenance proposal (approve or reject).

        If approved, the suggested_patch is applied to the affected backlog items.
        If rejected, the proposal is marked as rejected.

        Query params:
        - decision: "approved" or "rejected"
        """
        store = MaintenanceStore()
        config = load_config()
        service = BacklogService(config)

        proposal = store.resolve_proposal(proposal_id, decision=decision)
        if proposal is None:
            return JSONResponse(status_code=404, content={"error": "Proposal not found"})

        # Apply approved proposals to backlog items
        if decision == "approved" and proposal.suggested_patch:
            for idea_id in proposal.affected_idea_ids:
                service.update_item(idea_id, dict(proposal.suggested_patch))

        # Log to audit
        audit_store = AuditStore(config=config)
        for idea_id in proposal.affected_idea_ids:
            audit_store.log_backlog_mutation(
                event_type=AuditEventType.MAINTENANCE_PROPOSAL,
                idea_id=idea_id,
                actor=AuditActor.OPERATOR,
                patch={"proposal_id": proposal_id, "decision": decision},
                outcome=decision,
            )

        return JSONResponse(content=proposal.to_dict())

    @app.post("/api/content-gen/maintenance/jobs/{job_type}/trigger")
    async def trigger_maintenance_job(request: Request, job_type: str) -> JSONResponse:
        """Trigger a maintenance job immediately (on-demand).

        Path params:
        - job_type: one of stale_item_review, gap_summary, duplicate_watchlist, rescoring_recommend
        """
        try:
            job_type_enum = MaintenanceJobType(job_type)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"error": f"Unknown job type: {job_type}"},
            )

        # Use app-state scheduler if available (started with app lifecycle)
        runtime = getattr(request.app.state, "dashboard_runtime", None)
        scheduler: MaintenanceScheduler | None = None
        if runtime is not None:
            scheduler = getattr(runtime, "maintenance_scheduler", None)
        if scheduler is None:
            scheduler = MaintenanceScheduler()

        run = scheduler.trigger_job(job_type_enum)

        return JSONResponse(
            content={
                "run": run.to_dict(),
                "proposals_generated": run.proposals_count,
                "outcome": run.outcome,
                "error": run.error or None,
            }
        )

    @app.get("/api/content-gen/maintenance/runs")
    async def list_maintenance_runs(limit: int = 20) -> JSONResponse:
        """List recent maintenance run records."""
        store = MaintenanceStore()
        runs = store.load_runs(limit=limit)
        return JSONResponse(
            content={
                "items": [r.to_dict() for r in runs],
                "count": len(runs),
            }
        )

    # ------------------------------------------------------------------
    # WebSocket for pipeline progress
    # ------------------------------------------------------------------

    @app.websocket("/ws/content-gen/pipeline/{pipeline_id}")
    async def pipeline_websocket(websocket: WebSocket, pipeline_id: str) -> None:
        logger.info("Pipeline WS connecting pipeline_id=%s", pipeline_id)
        await websocket.accept()

        connection = WebSocketConnection(websocket, pipeline_id)
        await event_router.subscribe(pipeline_id, connection)

        # Send initial state
        job = job_registry.get_job(pipeline_id)
        if job is not None:
            initial: dict[str, Any] = {
                "type": "pipeline_status",
                "pipeline_id": pipeline_id,
                "status": str(job.status),
                "current_stage": (
                    job.pipeline_context.current_stage if job.pipeline_context else job.from_stage
                ),
            }
            if job.pipeline_context is not None:
                initial["context"] = json.loads(job.pipeline_context.model_dump_json())
            await connection.send_json(initial)

        try:
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type")
                if msg_type == "ping":
                    await connection.send_json({"type": "pong"})
                elif msg_type == "get_pipeline_status":
                    job = job_registry.get_job(pipeline_id)
                    if job is not None:
                        status_msg: dict[str, Any] = {
                            "type": "pipeline_status",
                            "pipeline_id": pipeline_id,
                            "status": str(job.status),
                        }
                        if job.pipeline_context is not None:
                            status_msg["context"] = json.loads(
                                job.pipeline_context.model_dump_json()
                            )
                        await connection.send_json(status_msg)
        except WebSocketDisconnect:
            logger.info("Pipeline WS disconnected pipeline_id=%s", pipeline_id)
        except Exception:
            logger.exception("Pipeline WS error pipeline_id=%s", pipeline_id)
        finally:
            await event_router.unsubscribe(pipeline_id, connection)


# ---------------------------------------------------------------------------
__all__ = ["register_content_gen_routes"]
