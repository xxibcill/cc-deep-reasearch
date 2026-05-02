"""FastAPI router for content generation pipeline endpoints."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any, Literal

logger = logging.getLogger(__name__)


# Backward-compatibility shim: tests that monkeypatch load_config on this module
# need the name to exist. Actual config loading is done via services.config.
def load_config() -> object:
    return object()


from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

from cc_deep_research.content_gen._serialization import model_list_to_json, model_to_json
from cc_deep_research.content_gen._services import ContentGenServices
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
from cc_deep_research.content_gen.models.backlog import BacklogItem
from cc_deep_research.content_gen.models.brief import OpportunityBrief
from cc_deep_research.content_gen.models.production import RunConstraints
from cc_deep_research.content_gen.models.shared import ReleaseState
from cc_deep_research.content_gen.progress import PipelineRunJobRegistry
from cc_deep_research.content_gen.storage import AuditActor, AuditEventType
from cc_deep_research.event_router import EventRouter, WebSocketConnection

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
    revision_id: str | None = Field(
        default=None, description="Specific revision to discuss (defaults to current head)"
    )
    mode: Literal["conversation", "edit"] = "edit"


class BriefAssistantApplyRequest(BaseModel):
    """Request body for brief-assistant apply endpoint."""

    proposals: list[BriefAssistantProposalInput] = Field(default_factory=list)
    revision_notes: str = Field(default="", description="Notes about what changed in this revision")


# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------


def register_content_gen_routes(
    app: FastAPI,
    event_router: EventRouter,
    job_registry: PipelineRunJobRegistry,
    services: ContentGenServices,
) -> None:
    """Register all content-gen API and WebSocket routes on *app*.

    Services must be pre-composed via build_content_gen_services() and passed
    in as *services*. Route handlers receive their dependencies through closure
    capture rather than constructing services inline.
    """
    from cc_deep_research.content_gen.backlog_api_service import (
        BacklogItemNotFoundError,
        BacklogValidationError,
        DuplicateActivePipelineError,
    )
    from cc_deep_research.content_gen.maintenance_api_service import (
        ProposalNotFoundError,
        UnknownJobTypeError,
    )
    from cc_deep_research.content_gen.pipeline_run_service import (
        PipelineNotActiveError,
        PipelineNotFoundError,
        ResumeContextError,
    )
    from cc_deep_research.content_gen.scripting_api_service import (
        ScriptContextNotFoundError,
        ScriptingApiError,
        ScriptMissingFieldsError,
        ScriptRunNotFoundError,
    )
    from cc_deep_research.content_gen.strategy_api_service import (
        RuleVersionNotFoundError,
    )

    service = services.pipeline_service
    backlog_api_service = services.backlog_api_service
    brief_api_service = services.brief_api_service
    scripting_api_service = services.scripting_api_service
    strategy_api_service = services.strategy_api_service
    publish_audit_service = services.publish_queue_audit_service
    maintenance_api_service = services.maintenance_api_service
    audit_store = services.audit_store

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
        try:
            result = service.stop_pipeline(pipeline_id)
            return JSONResponse(content=result)
        except PipelineNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Pipeline not found"})
        except PipelineNotActiveError:
            return JSONResponse(status_code=409, content={"error": "Pipeline is not active"})

    @app.post("/api/content-gen/pipelines/{pipeline_id}/resume")
    async def resume_pipeline(pipeline_id: str, request: ResumePipelineRequest) -> JSONResponse:
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
                    "completed_at": result.completed_at.isoformat()
                    if result.completed_at
                    else None,
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
                audit_store.log_operator_override(
                    idea_id=ctx.selected_idea_id,
                    original_state="blocked",
                    override_reason=request.override_reason,
                    actor=AuditActor.OPERATOR,
                    actor_label=request.actor,
                    pipeline_id=ctx.pipeline_id,
                    brief_id=ctx.brief_reference.brief_id if ctx.brief_reference else "",
                )
                if ctx.brief_reference:
                    services.brief_service.record_override(
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

    class GenerateVariantsRequest(BaseModel):
        tone: str | None = None
        cta_goal: str | None = None

    class UpdateScriptRequest(BaseModel):
        hook: str | None = None
        cta: str | None = None
        script: str | None = None

    @app.post("/api/content-gen/scripting")
    async def run_scripting(request: RunScriptingRequest) -> JSONResponse:
        try:
            result = await scripting_api_service.run_scripting(
                idea=request.idea,
                iterative_mode=request.iterative_mode,
                max_iterations=request.max_iterations,
                llm_route=request.llm_route,
            )
        except ScriptingApiError as exc:
            return JSONResponse(status_code=exc.status_code, content={"error": exc.message})
        return JSONResponse(content=scripting_api_service.serialize_result(result))

    @app.get("/api/content-gen/scripts")
    async def list_scripts() -> JSONResponse:
        items = scripting_api_service.list_scripts(limit=50)
        return JSONResponse(content={"items": items})

    @app.get("/api/content-gen/scripts/{run_id}")
    async def get_script(run_id: str) -> JSONResponse:
        try:
            result = scripting_api_service.get_script(run_id)
        except ScriptRunNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Script run not found"})
        return JSONResponse(content=scripting_api_service.serialize_result(result))

    @app.post("/api/content-gen/scripts/{run_id}/generate-variants")
    async def generate_script_variants(
        run_id: str,
        request: GenerateVariantsRequest,
    ) -> JSONResponse:
        """Generate new hook and CTA variants for an existing script run."""
        try:
            result = await scripting_api_service.generate_variants(
                run_id,
                tone=request.tone,
                cta_goal=request.cta_goal,
            )
        except ScriptRunNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Script run not found"})
        except ScriptContextNotFoundError as exc:
            return JSONResponse(status_code=exc.status_code, content={"error": exc.message})
        except ScriptMissingFieldsError as exc:
            return JSONResponse(status_code=exc.status_code, content={"error": exc.message})
        except ScriptingApiError as exc:
            return JSONResponse(status_code=exc.status_code, content={"error": exc.message})
        return JSONResponse(content=result)

    @app.patch("/api/content-gen/scripts/{run_id}")
    async def update_script(
        run_id: str,
        request: UpdateScriptRequest,
    ) -> JSONResponse:
        """Update a script run with new hook, CTA, or full script content."""
        try:
            result = scripting_api_service.update_script(
                run_id,
                hook=request.hook,
                cta=request.cta,
                script=request.script,
            )
        except ScriptRunNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Script run not found"})
        except ScriptContextNotFoundError as exc:
            return JSONResponse(status_code=exc.status_code, content={"error": exc.message})
        except ScriptingApiError as exc:
            return JSONResponse(status_code=exc.status_code, content={"error": exc.message})
        return JSONResponse(content=result)

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
            content=backlog_api_service.serialize_item(item),
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
        return JSONResponse(content=backlog_api_service.serialize_item(updated))

    @app.post("/api/content-gen/backlog/{idea_id}/select")
    async def select_backlog_item(idea_id: str) -> JSONResponse:
        try:
            selected = backlog_api_service.select_item(idea_id)
        except BacklogItemNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Backlog item not found"})
        return JSONResponse(content=backlog_api_service.serialize_item(selected))

    @app.post("/api/content-gen/backlog/{idea_id}/archive")
    async def archive_backlog_item(idea_id: str) -> JSONResponse:
        try:
            archived = backlog_api_service.archive_item(idea_id)
        except BacklogItemNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Backlog item not found"})
        return JSONResponse(content=backlog_api_service.serialize_item(archived))

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

    from cc_deep_research.content_gen.brief_api_service import (
        BriefConcurrentModificationError,
        BriefNotFoundError,
        BriefValidationError,
    )

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
        try:
            result = brief_api_service.list_briefs(lifecycle_state=lifecycle_state, limit=limit)
        except BriefValidationError as exc:
            return JSONResponse(status_code=400, content={"error": exc.message})
        return JSONResponse(content=brief_api_service.serialize_list(result))

    @app.post("/api/content-gen/briefs", status_code=201)
    async def create_brief(request: CreateBriefRequest) -> JSONResponse:
        """Create a new managed brief from an OpportunityBrief payload.

        This creates a new brief resource with a single initial revision.
        The brief starts in DRAFT state.
        """
        try:
            managed = brief_api_service.create_brief(
                request.brief,
                provenance=request.provenance,
                source_pipeline_id=request.source_pipeline_id,
                revision_notes=request.revision_notes,
            )
        except BriefValidationError as exc:
            return JSONResponse(status_code=400, content={"error": exc.message})
        return JSONResponse(content=model_to_json(managed))

    @app.get("/api/content-gen/briefs/{brief_id}")
    async def get_brief(brief_id: str) -> JSONResponse:
        """Get a single brief with its current head revision content."""
        try:
            managed, revision = brief_api_service.get_brief_with_revision(brief_id)
        except BriefNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})
        return JSONResponse(
            content=brief_api_service.serialize_brief_with_revision(managed, revision)
        )

    @app.patch("/api/content-gen/briefs/{brief_id}")
    async def update_brief(brief_id: str, request: UpdateBriefRequest) -> JSONResponse:
        """Update brief metadata (title, etc.).

        Note: Use save_revision() to create new content revisions.
        """
        try:
            updated = brief_api_service.update_brief(
                brief_id,
                request.patch,
                expected_updated_at=request.expected_updated_at,
            )
        except BriefConcurrentModificationError as exc:
            return JSONResponse(
                status_code=409,
                content={
                    "error": exc.message,
                    "expected_updated_at": exc.expected_updated_at,
                    "actual_updated_at": exc.actual_updated_at,
                },
            )
        except BriefNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})
        except BriefValidationError as exc:
            return JSONResponse(status_code=400, content={"error": exc.message})
        return JSONResponse(content=model_to_json(updated))

    @app.get("/api/content-gen/briefs/{brief_id}/revisions")
    async def list_brief_revisions(brief_id: str, limit: int = 50) -> JSONResponse:
        """List all revisions for a brief, most recent first."""
        try:
            revisions = brief_api_service.list_revisions(brief_id, limit=limit)
        except BriefNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})
        return JSONResponse(
            content={
                "items": model_list_to_json(revisions),
                "count": len(revisions),
            }
        )

    @app.get("/api/content-gen/briefs/{brief_id}/revisions/{revision_id}")
    async def get_brief_revision(brief_id: str, revision_id: str) -> JSONResponse:
        """Get a specific revision by ID."""
        revision = brief_api_service.get_revision(revision_id)
        if revision is None or revision.brief_id != brief_id:
            return JSONResponse(status_code=404, content={"error": "Revision not found"})
        return JSONResponse(content=model_to_json(revision))

    @app.post("/api/content-gen/briefs/{brief_id}/revisions")
    async def save_brief_revision(brief_id: str, request: SaveRevisionRequest) -> JSONResponse:
        """Save a new revision of an existing brief.

        The current_revision_id (head) is NOT changed by this operation.
        Use /apply-revision to promote a revision to head.
        """
        try:
            revision = brief_api_service.save_revision(
                brief_id,
                request.brief,
                revision_notes=request.revision_notes,
                source_pipeline_id=request.source_pipeline_id,
                expected_updated_at=request.expected_updated_at,
            )
        except BriefConcurrentModificationError as exc:
            return JSONResponse(
                status_code=409,
                content={
                    "error": exc.message,
                    "expected_updated_at": exc.expected_updated_at,
                    "actual_updated_at": exc.actual_updated_at,
                },
            )
        except BriefNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})
        except BriefValidationError as exc:
            return JSONResponse(status_code=400, content={"error": exc.message})
        return JSONResponse(content=model_to_json(revision), status_code=201)

    @app.post("/api/content-gen/briefs/{brief_id}/apply-revision")
    async def apply_revision(brief_id: str, request: ApplyRevisionRequest) -> JSONResponse:
        """Apply a revision as the current head (promote it to active)."""
        try:
            updated = brief_api_service.update_head(
                brief_id,
                request.revision_id,
                expected_updated_at=request.expected_updated_at,
            )
        except BriefConcurrentModificationError as exc:
            return JSONResponse(
                status_code=409,
                content={
                    "error": exc.message,
                    "expected_updated_at": exc.expected_updated_at,
                    "actual_updated_at": exc.actual_updated_at,
                },
            )
        except BriefNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})
        return JSONResponse(content=model_to_json(updated))

    @app.post("/api/content-gen/briefs/{brief_id}/approve")
    async def approve_brief(brief_id: str, expected_updated_at: str | None = None) -> JSONResponse:
        """Transition a brief to the approved state."""
        try:
            updated = brief_api_service.approve_brief(
                brief_id, expected_updated_at=expected_updated_at
            )
        except BriefConcurrentModificationError as exc:
            return JSONResponse(
                status_code=409,
                content={
                    "error": exc.message,
                    "expected_updated_at": exc.expected_updated_at,
                    "actual_updated_at": exc.actual_updated_at,
                },
            )
        except BriefNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})
        return JSONResponse(content=model_to_json(updated))

    @app.post("/api/content-gen/briefs/{brief_id}/archive")
    async def archive_brief(brief_id: str, expected_updated_at: str | None = None) -> JSONResponse:
        """Archive a brief."""
        try:
            updated = brief_api_service.archive_brief(
                brief_id, expected_updated_at=expected_updated_at
            )
        except BriefConcurrentModificationError as exc:
            return JSONResponse(
                status_code=409,
                content={
                    "error": exc.message,
                    "expected_updated_at": exc.expected_updated_at,
                    "actual_updated_at": exc.actual_updated_at,
                },
            )
        except BriefNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})
        return JSONResponse(content=model_to_json(updated))

    @app.post("/api/content-gen/briefs/{brief_id}/supersede")
    async def supersede_brief(
        brief_id: str, expected_updated_at: str | None = None
    ) -> JSONResponse:
        """Mark a brief as superseded."""
        try:
            updated = brief_api_service.supersede_brief(
                brief_id, expected_updated_at=expected_updated_at
            )
        except BriefConcurrentModificationError as exc:
            return JSONResponse(
                status_code=409,
                content={
                    "error": exc.message,
                    "expected_updated_at": exc.expected_updated_at,
                    "actual_updated_at": exc.actual_updated_at,
                },
            )
        except BriefNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})
        return JSONResponse(content=model_to_json(updated))

    @app.post("/api/content-gen/briefs/{brief_id}/revert-to-draft")
    async def revert_brief_to_draft(
        brief_id: str, expected_updated_at: str | None = None
    ) -> JSONResponse:
        """Revert a brief back to draft state."""
        try:
            updated = brief_api_service.revert_to_draft(
                brief_id, expected_updated_at=expected_updated_at
            )
        except BriefConcurrentModificationError as exc:
            return JSONResponse(
                status_code=409,
                content={
                    "error": exc.message,
                    "expected_updated_at": exc.expected_updated_at,
                    "actual_updated_at": exc.actual_updated_at,
                },
            )
        except BriefNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})
        return JSONResponse(content=model_to_json(updated))

    @app.post("/api/content-gen/briefs/{brief_id}/clone")
    async def clone_brief(brief_id: str, request: CloneBriefRequest) -> JSONResponse:
        """Clone an existing brief.

        The clone starts with the same current head revision but is otherwise
        independent. Returns the new brief in DRAFT state.
        """
        try:
            cloned = brief_api_service.clone_brief(brief_id, new_title=request.new_title)
        except BriefNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})
        return JSONResponse(content=model_to_json(cloned), status_code=201)

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
        try:
            entries = brief_api_service.get_audit_history(
                brief_id=brief_id,
                event_type=event_type,
                actor=actor,
                limit=limit,
            )
        except BriefNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})
        return JSONResponse(
            content={
                "brief_id": brief_id,
                "items": entries,
                "count": len(entries),
            }
        )

    # ------------------------------------------------------------------
    # Brief Assistant (Phase 05)
    # ------------------------------------------------------------------

    from cc_deep_research.content_gen.agents.brief_assistant import (
        BriefAssistantAgent,
        build_apply_proposals,
    )

    @app.post("/api/content-gen/briefs/{brief_id}/assistant/respond")
    async def brief_assistant_respond(
        brief_id: str, request: BriefAssistantRespondRequest
    ) -> JSONResponse:
        """Generate a conversational response with optional brief revision proposals.

        This endpoint is advisory only — it never writes to persistent state.
        Use /apply to persist any proposed revisions.
        """
        try:
            managed = brief_api_service.get_brief(brief_id)
        except BriefNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})

        # Load the revision to discuss
        revision_id = request.revision_id or managed.current_revision_id
        revision = brief_api_service.get_revision(revision_id)
        if revision is None or revision.brief_id != brief_id:
            return JSONResponse(status_code=404, content={"error": "Revision not found"})

        agent = BriefAssistantAgent(config=services.config)
        messages = [{"role": m.role, "content": m.content} for m in request.messages]

        response = await agent.respond(
            messages=messages,
            brief_revision=revision,
            mode=request.mode,
        )

        return JSONResponse(content=model_to_json(response))

    @app.post("/api/content-gen/briefs/{brief_id}/assistant/apply")
    async def brief_assistant_apply(
        brief_id: str, request: BriefAssistantApplyRequest
    ) -> JSONResponse:
        """Apply a list of validated brief revision proposals.

        This is the only write path for assistant-proposed revisions.
        Returns structured errors instead of crashing on invalid proposals.
        """
        try:
            managed, _ = brief_api_service.get_brief_with_revision(brief_id)
        except BriefNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})

        # Build the opportunity from merged proposals
        current_revision = brief_api_service.get_revision(managed.current_revision_id)
        if current_revision is None:
            return JSONResponse(
                status_code=400, content={"error": "No current revision to base changes on"}
            )

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
            revision = brief_api_service.save_revision(
                brief_id,
                opportunity.model_dump(),
                revision_notes=request.revision_notes or "AI-assisted revision",
                source_pipeline_id="",
            )
        except Exception as exc:
            return JSONResponse(status_code=400, content={"error": str(exc), "applied": 0})
        except BriefNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})
        except BriefConcurrentModificationError as exc:
            return JSONResponse(status_code=409, content={"error": exc.message, "applied": 0})
        except BriefValidationError as exc:
            return JSONResponse(status_code=400, content={"error": exc.message, "applied": 0})

        # Log the assistant origin
        if brief_api_service._audit_store is not None:
            brief_api_service._audit_store.log_brief_mutation(
                event_type=AuditEventType.BRIEF_REVISION_SAVED,
                brief_id=brief_id,
                actor=AuditActor.AI_PROPOSAL,
                patch={"revision_id": revision.revision_id, "proposals_count": applied_count},
                brief_snapshot=managed,
                outcome="success",
            )

        return JSONResponse(
            status_code=201,
            content={
                "applied": applied_count,
                "revision": model_to_json(revision) if revision else None,
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
        try:
            managed, revision = brief_api_service.get_brief_with_revision(brief_id)
        except BriefNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})

        if revision is None:
            return JSONResponse(status_code=400, content={"error": "No current revision found"})

        result = await generate_backlog_from_brief(revision)

        return JSONResponse(content=model_to_json(result))

    @app.post("/api/content-gen/briefs/{brief_id}/apply-backlog")
    async def apply_backlog_from_brief(
        brief_id: str,
        items: list[dict[str, Any]],
    ) -> JSONResponse:
        """Apply generated backlog items from a brief to the persistent backlog.

        This persists items to the backlog with trace links back to the brief.
        """
        try:
            managed, revision = brief_api_service.get_brief_with_revision(brief_id)
        except BriefNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})

        if revision is None:
            return JSONResponse(status_code=400, content={"error": "No current revision found"})

        backlog_service = services.backlog_service

        applied_count, created_items, errors = brief_api_service.apply_backlog_items(
            brief_id,
            items,
            backlog_service,
        )

        return JSONResponse(
            content={
                "applied": applied_count,
                "items": model_list_to_json(created_items),
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
        try:
            branched = brief_api_service.branch_brief(
                brief_id,
                new_title=request.new_title,
                branch_reason=request.branch_reason,
            )
        except BriefNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})
        return JSONResponse(content=model_to_json(branched), status_code=201)

    @app.get("/api/content-gen/briefs/{brief_id}/siblings")
    async def list_sibling_briefs(brief_id: str) -> JSONResponse:
        """List briefs that share the same source brief.

        Returns all briefs that were branched from the same source,
        including the source brief itself.
        """
        try:
            siblings = brief_api_service.list_sibling_briefs(brief_id)
        except BriefNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Brief not found"})

        return JSONResponse(
            content={
                "items": model_list_to_json(siblings),
                "count": len(siblings),
            }
        )

    @app.get("/api/content-gen/briefs/{brief_id}/compare/{other_brief_id}")
    async def compare_briefs(brief_id: str, other_brief_id: str) -> JSONResponse:
        """Compare two briefs side by side.

        Returns both briefs with their current head revisions for comparison.
        """
        try:
            brief_a, revision_a, brief_b, revision_b = brief_api_service.compare_briefs(
                brief_id, other_brief_id
            )
        except BriefNotFoundError:
            return JSONResponse(status_code=404, content={"error": "One or both briefs not found"})

        return JSONResponse(
            content={
                "brief_a": model_to_json(brief_a),
                "brief_b": model_to_json(brief_b),
                "revision_a": model_to_json(revision_a) if revision_a else None,
                "revision_b": model_to_json(revision_b) if revision_b else None,
            }
        )

    # ------------------------------------------------------------------
    # Backlog chat
    # ------------------------------------------------------------------

    @app.post("/api/content-gen/backlog-chat/respond")
    async def backlog_chat_respond(request: BacklogChatRespondRequest) -> JSONResponse:
        """Generate a conversational response with optional backlog operations.

        This endpoint is advisory only — it never writes to the backlog.
        Use /apply to persist any proposed operations.
        """
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        backlog_items = (
            request.backlog_items
            if request.backlog_items
            else services.backlog_service.load().items
        )

        agent = BacklogChatAgent(services.config)
        response = await agent.respond(
            messages=messages,
            backlog_items=backlog_items,
            strategy=request.strategy,
            selected_idea_id=request.selected_idea_id,
            mode=request.mode,
        )

        return JSONResponse(content=model_to_json(response))

    @app.post("/api/content-gen/backlog-chat/apply")
    async def backlog_chat_apply(request: BacklogChatApplyRequest) -> JSONResponse:
        """Apply a list of validated backlog operations.

        This is the only write path for chat-proposed operations.
        Returns structured errors instead of crashing on invalid operations.
        """
        backlog_items = services.backlog_service.load().items
        operations, errors = build_apply_operations(
            [op.model_dump(mode="python") for op in request.operations],
            backlog_items,
        )
        applied = 0
        items: list[BacklogItem] = []
        if operations:
            applied, items, apply_errors = await apply_operations(
                operations, services.backlog_service
            )
            errors.extend(apply_errors)

        return JSONResponse(
            content={
                "applied": applied,
                "items": model_list_to_json(items),
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
        backlog_items = (
            request.backlog_items
            if request.backlog_items
            else services.backlog_service.load().items
        )

        agent = BatchTriageAgent(services.config)
        response = await agent.respond(
            backlog_items=backlog_items,
            strategy=request.strategy,
        )

        return JSONResponse(content=model_to_json(response))

    @app.post("/api/content-gen/backlog-ai/triage/apply")
    async def backlog_triage_apply(request: TriageApplyRequest) -> JSONResponse:
        """Apply a list of validated triage operations.

        This is the only write path for triage-proposed operations.
        Returns structured errors instead of crashing on invalid operations.
        """
        backlog_items = services.backlog_service.load().items
        operations, errors = build_triage_apply_operations(
            [op.model_dump(mode="python") for op in request.operations],
            backlog_items,
        )
        applied = 0
        items: list[BacklogItem] = []
        if operations:
            applied, items, apply_errors = await apply_triage_operations(
                operations, services.backlog_service
            )
            errors.extend(apply_errors)

        return JSONResponse(
            content={
                "applied": applied,
                "items": model_list_to_json(items),
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
        backlog = services.backlog_service.load()

        item = next((i for i in backlog.items if i.idea_id == request.idea_id), None)
        if item is None:
            return JSONResponse(status_code=404, content={"error": "Backlog item not found"})

        agent = NextActionAgent(services.config)
        response = await agent.recommend(
            item,
            strategy_context=request.strategy,
        )

        return JSONResponse(content=model_to_json(response))

    @app.post("/api/content-gen/backlog-ai/next-action/batch")
    async def get_next_action_batch(
        request: TriageRespondRequest,
    ) -> JSONResponse:
        """Get next-action recommendations for multiple backlog items.

        Returns recommendations for all items in the request (or all items
        in the backlog if none provided).
        """
        backlog_items = (
            request.backlog_items
            if request.backlog_items
            else services.backlog_service.load().items
        )

        recommendations = []
        warnings: list[str] = []

        for item in backlog_items:
            agent = NextActionAgent(services.config)
            try:
                response = await agent.recommend(
                    item,
                    strategy_context=request.strategy,
                )
                recommendations.append(model_to_json(response))
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
        backlog = services.backlog_service.load()

        item = next((i for i in backlog.items if i.idea_id == request.idea_id), None)
        if item is None:
            return JSONResponse(status_code=404, content={"error": "Backlog item not found"})

        agent = ExecutionBriefAgent(services.config)
        response = await agent.generate_brief(
            item,
            strategy_context=request.strategy,
        )

        return JSONResponse(content=model_to_json(response))

    # ------------------------------------------------------------------
    # Strategy
    # ------------------------------------------------------------------

    @app.get("/api/content-gen/strategy")
    async def get_strategy() -> JSONResponse:
        memory = strategy_api_service.get_strategy()
        return JSONResponse(content=strategy_api_service.serialize_strategy(memory))

    @app.put("/api/content-gen/strategy")
    async def update_strategy(request: UpdateStrategyRequest) -> JSONResponse:
        updated = strategy_api_service.update_strategy(request.patch)
        return JSONResponse(content=strategy_api_service.serialize_strategy(updated))

    @app.get("/api/content-gen/strategy/readiness")
    async def get_strategy_readiness() -> JSONResponse:
        """Check strategy readiness and return validation results.

        P4-T1: Returns blocking and warning issues so operators can see
        which fields or ratios are causing readiness failures.
        """
        result = strategy_api_service.check_readiness()
        return JSONResponse(content=strategy_api_service.serialize_readiness(result))

    @app.get("/api/content-gen/strategy/rules-for-review")
    async def get_rules_for_review() -> JSONResponse:
        """Get all rules that need operator review.

        P4-T2: Returns rules that are under_review, expired, or past their
        review date.
        """
        rules = strategy_api_service.get_rules_for_review()
        return JSONResponse(
            content={
                "items": [strategy_api_service.serialize_rule_version(r) for r in rules],
                "count": len(rules),
            }
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
        try:
            version = strategy_api_service.update_rule_lifecycle(
                version_id,
                status=status,
                confidence=confidence,
                evidence_count=evidence_count,
                review_after=review_after,
                review_notes=review_notes,
            )
        except RuleVersionNotFoundError:
            return JSONResponse(
                content={"error": "Rule version not found"},
                status_code=404,
            )
        return JSONResponse(content=strategy_api_service.serialize_rule_version(version))

    @app.get("/api/content-gen/learnings")
    async def list_learnings(
        category: str | None = None,
        durability: str | None = None,
    ) -> JSONResponse:
        items, count = strategy_api_service.list_learnings(category=category, durability=durability)
        return JSONResponse(
            content={
                "items": [strategy_api_service.serialize_learning(item) for item in items],
                "count": count,
            }
        )

    @app.post("/api/content-gen/learnings/apply")
    async def apply_learnings(request: ApplyLearningsRequest) -> JSONResponse:
        guidance = strategy_api_service.apply_learnings(
            request.learning_ids,
            operator_approved=request.operator_approved,
        )
        return JSONResponse(content=model_to_json(guidance))

    @app.get("/api/content-gen/rule-versions")
    async def list_rule_versions(kind: str | None = None) -> JSONResponse:
        items = strategy_api_service.list_rule_versions(kind=kind)
        return JSONResponse(content=items)

    @app.get("/api/content-gen/operating-fitness")
    async def get_operating_fitness() -> JSONResponse:
        result = strategy_api_service.get_operating_fitness()
        return JSONResponse(content=result)

    # ------------------------------------------------------------------
    # Publish queue
    # ------------------------------------------------------------------

    @app.get("/api/content-gen/publish")
    async def list_publish_queue() -> JSONResponse:
        items = publish_audit_service.list_publish_queue()
        return JSONResponse(
            content={"items": [publish_audit_service.serialize_publish_item(i) for i in items]}
        )

    @app.delete("/api/content-gen/publish/{idea_id}/{platform}")
    async def remove_from_queue(idea_id: str, platform: str) -> JSONResponse:
        removed = publish_audit_service.remove_from_queue(idea_id, platform)
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
        entries, count = publish_audit_service.list_audit_entries(
            idea_id=idea_id,
            event_type=event_type,
            actor=actor,
            limit=limit,
        )
        return JSONResponse(content={"items": entries, "count": count})

    @app.get("/api/content-gen/audit/{idea_id}")
    async def get_audit_for_item(idea_id: str, limit: int = 50) -> JSONResponse:
        """Get audit history for a specific backlog item."""
        entries, count = publish_audit_service.get_audit_for_item(idea_id=idea_id, limit=limit)
        return JSONResponse(content={"idea_id": idea_id, "items": entries, "count": count})

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
        proposals, count = maintenance_api_service.list_proposals(
            status=status,
            job_type=job_type,
            limit=limit,
        )
        return JSONResponse(content={"items": proposals, "count": count})

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
        try:
            result = maintenance_api_service.resolve_proposal(proposal_id, decision=decision)
        except ProposalNotFoundError:
            return JSONResponse(status_code=404, content={"error": "Proposal not found"})
        return JSONResponse(content=result)

    @app.post("/api/content-gen/maintenance/jobs/{job_type}/trigger")
    async def trigger_maintenance_job(request: Request, job_type: str) -> JSONResponse:
        """Trigger a maintenance job immediately (on-demand).

        Path params:
        - job_type: one of stale_item_review, gap_summary, duplicate_watchlist, rescoring_recommend
        """
        # Use app-state scheduler if available (started with app lifecycle)
        runtime = getattr(request.app.state, "dashboard_runtime", None)
        scheduler = None
        if runtime is not None:
            scheduler = getattr(runtime, "maintenance_scheduler", None)

        try:
            result = maintenance_api_service.trigger_job(job_type, scheduler=scheduler)
        except UnknownJobTypeError as exc:
            return JSONResponse(status_code=400, content={"error": exc.message})
        return JSONResponse(content=result)

    @app.get("/api/content-gen/maintenance/runs")
    async def list_maintenance_runs(limit: int = 20) -> JSONResponse:
        """List recent maintenance run records."""
        runs, count = maintenance_api_service.list_runs(limit=limit)
        return JSONResponse(content={"items": runs, "count": count})

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
                initial["context"] = model_to_json(job.pipeline_context)
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
