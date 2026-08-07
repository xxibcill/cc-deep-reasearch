"""Planner-based research orchestrator for the hierarchical workflow."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

from cc_deep_research.agents import (
    AnalyzerAgent,
    PlannerAgent,
    ReporterAgent,
    SourceCollectorAgent,
    ValidatorAgent,
)
from cc_deep_research.config import Config
from cc_deep_research.llm import LLMRouter, LLMRouteRegistry
from cc_deep_research.models import (
    AnalysisResult,
    PlannerResult,
    PlanSynthesis,
    ResearchDepth,
    ResearchPlan,
    ResearchSession,
    SearchResultItem,
    StrategyResult,
    TaskExecutionResult,
    ValidationResult,
)
from cc_deep_research.models.checkpoint import CheckpointOperation
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.orchestration.session_builder import SessionBuilder
from cc_deep_research.orchestration.task_dispatcher import TaskDispatcher
from cc_deep_research.research_runs.models import (
    ResearchRunCancelled,
    ResearchRunRequest,
    ResearchWorkflow,
)
from cc_deep_research.research_runs.resume import (
    ResearchResumePhase,
    ResearchResumeState,
    ResearchResumeStore,
    build_config_fingerprint,
)

if TYPE_CHECKING:
    from cc_deep_research.llm.codex_runtime import CodexRuntime


class PlannerResearchOrchestrator:
    """Orchestrator that uses the planner-based workflow.

    This orchestrator uses a hierarchical approach:
    1. Planner Agent analyzes the query and creates a plan with subtasks
    2. Task Dispatcher executes subtasks in parallel when possible
    3. Results are synthesized into a final research report

    This is an alternative to the staged pipeline (TeamResearchOrchestrator),
    offering more flexibility for complex, multi-faceted research queries.
    """

    def __init__(
        self,
        config: Config,
        monitor: ResearchMonitor | None = None,
        prompt_registry: Any | None = None,
        workflow_config: Any | None = None,
        codex_runtime: CodexRuntime | None = None,
        run_request: ResearchRunRequest | None = None,
        resume_store: ResearchResumeStore | None = None,
        config_fingerprint: str | None = None,
    ) -> None:
        """Initialize the planner orchestrator.

        Args:
            config: Application configuration.
            monitor: Optional research monitor for progress tracking.
            prompt_registry: Optional prompt registry with overrides applied.
            workflow_config: Optional theme workflow configuration.
            codex_runtime: Optional Codex runtime owned by the calling application.
        """
        self._config = config
        self._monitor = monitor or ResearchMonitor(enabled=False)
        self._prompt_registry = prompt_registry
        self._workflow_config = workflow_config
        self._llm_registry = LLMRouteRegistry(config.llm)
        self._llm_router = LLMRouter(
            self._llm_registry,
            monitor=self._monitor,
            codex_runtime=codex_runtime,
        )
        self._planner = PlannerAgent(config.model_dump())
        self._dispatcher: TaskDispatcher | None = None
        self._agents: dict[str, Any] = {}
        self._session_builder = SessionBuilder()
        self._provider_metadata: dict[str, Any] = {"configured": [], "available": [], "warnings": []}
        self._execution_degradations: list[str] = []
        self._llm_routes: dict[str, Any] = {"planned_routes": {}, "actual_routes": {}, "usage_stats": {}, "fallback_events": []}
        self._iteration_history: list[dict[str, Any]] = []
        self._run_request = run_request
        self._resume_store = resume_store or ResearchResumeStore()
        self._config_fingerprint = config_fingerprint or build_config_fingerprint(config)

    async def execute_research(
        self,
        query: str,
        depth: ResearchDepth,
        min_sources: int | None = None,
        phase_hook: Callable[[str, str], None] | None = None,
        cancellation_check: Callable[[], None] | None = None,
        on_session_started: Callable[[str], None] | None = None,
    ) -> ResearchSession:
        """Execute research using the planner workflow."""
        if self._run_request is None:
            self._run_request = ResearchRunRequest(
                query=query,
                depth=depth,
                min_sources=min_sources,
                workflow=ResearchWorkflow.PLANNER,
            )
        return await self._execute_research(
            query=query,
            depth=depth,
            min_sources=min_sources,
            phase_hook=phase_hook,
            cancellation_check=cancellation_check,
            on_session_started=on_session_started,
            resume_state=None,
        )

    async def resume_research(
        self,
        state: ResearchResumeState,
        *,
        phase_hook: Callable[[str, str], None] | None = None,
        cancellation_check: Callable[[], None] | None = None,
        on_session_started: Callable[[str], None] | None = None,
    ) -> ResearchSession:
        """Continue a planner run without repeating completed task groups."""
        if state.workflow != ResearchWorkflow.PLANNER:
            raise ValueError("Planner execution cannot resume a staged snapshot")
        if state.config_fingerprint != self._config_fingerprint:
            raise ValueError("Research configuration changed since the checkpoint was created")
        if self._run_request is None:
            self._run_request = state.request.model_copy(deep=True)
        return await self._execute_research(
            query=state.query,
            depth=state.depth,
            min_sources=state.min_sources,
            phase_hook=phase_hook,
            cancellation_check=cancellation_check,
            on_session_started=on_session_started,
            resume_state=state,
        )

    async def _execute_research(
        self,
        *,
        query: str,
        depth: ResearchDepth,
        min_sources: int | None,
        phase_hook: Callable[[str, str], None] | None,
        cancellation_check: Callable[[], None] | None,
        on_session_started: Callable[[str], None] | None,
        resume_state: ResearchResumeState | None,
    ) -> ResearchSession:
        """Run a new or restored planner workflow from a durable boundary."""
        start_time = datetime.utcnow()
        session_id = self._initialize_session(
            query=query,
            depth=depth,
            on_session_started=on_session_started,
        )

        # Emit session start event with workflow context
        self._monitor.emit_event(
            event_type="session.started",
            category="session",
            name="planner-research",
            status="started",
            metadata={
                "workflow": "planner",
                "query": query,
                "depth": depth.value if hasattr(depth, 'value') else str(depth),
                "original_session_id": (
                    resume_state.origin_session_id if resume_state is not None else None
                ),
            },
        )

        # Check cancellation before starting
        if cancellation_check:
            cancellation_check()

        try:
            next_phase = (
                resume_state.next_phase
                if resume_state is not None
                else ResearchResumePhase.PLANNER_PLAN
            )
            planner_result = resume_state.planner_result if resume_state is not None else None
            task_results = (
                dict(resume_state.planner_task_results) if resume_state is not None else {}
            )
            synthesis = resume_state.planner_synthesis if resume_state is not None else None

            if next_phase == ResearchResumePhase.PLANNER_PLAN:
                self._notify_phase(phase_hook, "planning", "Creating research plan")
                if cancellation_check:
                    cancellation_check()
                planner_result = await self._create_plan(query, depth)
                self._persist_planner_state(
                    session_id=session_id,
                    query=query,
                    depth=depth,
                    min_sources=min_sources,
                    next_phase=ResearchResumePhase.PLANNER_EXECUTION,
                    planner_result=planner_result,
                    task_results={},
                    resume_state=resume_state,
                )

            if planner_result is None:
                raise ValueError("Resume state is missing the research plan")
            plan = planner_result.plan

            if next_phase != ResearchResumePhase.COMPLETE:
                self._notify_phase(phase_hook, "init", "Initializing agents")
                if cancellation_check:
                    cancellation_check()
                await self._initialize_agents(depth)

            if next_phase in {
                ResearchResumePhase.PLANNER_PLAN,
                ResearchResumePhase.PLANNER_EXECUTION,
            }:
                self._notify_phase(phase_hook, "execution", "Executing research plan")
                if cancellation_check:
                    cancellation_check()

                async def persist_group(
                    current_results: dict[str, TaskExecutionResult],
                ) -> None:
                    self._persist_planner_state(
                        session_id=session_id,
                        query=query,
                        depth=depth,
                        min_sources=min_sources,
                        next_phase=ResearchResumePhase.PLANNER_EXECUTION,
                        planner_result=planner_result,
                        task_results=current_results,
                        resume_state=resume_state,
                    )

                task_results = await self._execute_plan(
                    plan,
                    cancellation_check=cancellation_check,
                    initial_results=task_results,
                    group_completed_callback=persist_group,
                )
                if cancellation_check:
                    cancellation_check()
                self._persist_planner_state(
                    session_id=session_id,
                    query=query,
                    depth=depth,
                    min_sources=min_sources,
                    next_phase=ResearchResumePhase.PLANNER_SYNTHESIS,
                    planner_result=planner_result,
                    task_results=task_results,
                    resume_state=resume_state,
                )

            if next_phase != ResearchResumePhase.COMPLETE:
                self._notify_phase(phase_hook, "synthesis", "Synthesizing results")
                if cancellation_check:
                    cancellation_check()
                synthesis = self._synthesize_results(plan, task_results)
                self._persist_planner_state(
                    session_id=session_id,
                    query=query,
                    depth=depth,
                    min_sources=min_sources,
                    next_phase=ResearchResumePhase.COMPLETE,
                    planner_result=planner_result,
                    task_results=task_results,
                    synthesis=synthesis,
                    resume_state=resume_state,
                )

            if synthesis is None:
                raise ValueError("Resume state is missing the planner synthesis")

            # Phase 5: Build session
            self._notify_phase(phase_hook, "complete", "Research complete")
            session = self._build_session(
                session_id=session_id,
                query=query,
                depth=depth,
                plan=plan,
                synthesis=synthesis,
                planner_result=planner_result,
                started_at=start_time,
                min_sources=min_sources,
            )
            if resume_state is not None:
                session.metadata["resume"] = {
                    "original_session_id": resume_state.origin_session_id,
                    "resumed_from_checkpoint_id": resume_state.origin_checkpoint_id,
                    "resumed_phase": resume_state.next_phase.value,
                }

            self._monitor.log(f"Research complete: {len(synthesis.all_sources)} sources, {len(synthesis.key_findings)} findings")

            # Emit session complete event
            self._monitor.finalize_session(
                total_sources=len(synthesis.all_sources),
                providers=list(self._provider_metadata.get("available", [])),
                total_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
                status="completed",
                stop_reason="success",
            )

            return session

        except ResearchRunCancelled:
            raise
        except Exception as exc:
            self._monitor.log(f"Research failed: {exc}")
            # Emit failed session event
            if self._monitor.session_id:
                self._monitor.finalize_session(
                    total_sources=0,
                    providers=list(self._provider_metadata.get("available", [])),
                    total_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
                    status="failed",
                    stop_reason="error",
                )
            raise PlannerOrchestratorError(
                f"Research execution failed: {exc}",
                query=query,
                original_error=exc,
            ) from exc

        finally:
            await self._cleanup()

    def _persist_planner_state(
        self,
        *,
        session_id: str,
        query: str,
        depth: ResearchDepth,
        min_sources: int | None,
        next_phase: ResearchResumePhase,
        planner_result: PlannerResult,
        task_results: dict[str, TaskExecutionResult],
        synthesis: PlanSynthesis | None = None,
        resume_state: ResearchResumeState | None,
    ) -> str | None:
        """Persist the planner graph and completed task outputs atomically."""
        if self._run_request is None:
            return None
        state = ResearchResumeState(
            workflow=ResearchWorkflow.PLANNER,
            query=query,
            depth=depth,
            min_sources=min_sources,
            next_phase=next_phase,
            request=self._run_request,
            config_fingerprint=self._config_fingerprint,
            planner_result=planner_result,
            planner_task_results=task_results,
            planner_synthesis=synthesis,
            origin_session_id=(
                resume_state.origin_session_id if resume_state is not None else session_id
            ),
            origin_checkpoint_id=(
                resume_state.origin_checkpoint_id if resume_state is not None else None
            ),
        )
        snapshot = self._resume_store.save(session_id, state)
        return self._monitor.emit_checkpoint(
            phase=next_phase.value,
            operation=CheckpointOperation.FINALIZE.value,
            output_ref={
                "next_phase": next_phase.value,
                "completed_tasks": sum(result.success for result in task_results.values()),
                "task_count": len(planner_result.plan.subtasks),
            },
            state_ref=snapshot.path,
            artifact_refs=[
                {
                    "kind": "resume_state",
                    "path": snapshot.path,
                    "content_hash": snapshot.content_hash,
                    "size_bytes": snapshot.size_bytes,
                }
            ],
            replayable=True,
            metadata={"execution_resume": True, "workflow": ResearchWorkflow.PLANNER.value},
        )

    def _initialize_session(
        self,
        *,
        query: str,
        depth: ResearchDepth,
        on_session_started: Callable[[str], None] | None,
    ) -> str:
        """Initialize the research session."""
        self._monitor.section("Planner Research Session")
        self._monitor.log(f"Query: {query}")
        self._monitor.log(f"Depth: {depth.value}")

        session_id = f"planner-{uuid.uuid4().hex[:12]}"
        self._monitor.log(f"Session ID: {session_id}")
        self._monitor.set_session(
            session_id=session_id,
            query=query,
            depth=depth.value,
            concurrent_source_collection=False,
            configured_researchers=1,
        )

        if on_session_started:
            on_session_started(session_id)

        return session_id

    async def _create_plan(
        self,
        query: str,
        depth: ResearchDepth,
    ) -> PlannerResult:
        """Create the research plan using the Planner Agent."""
        self._monitor.section("Planning")

        planner_result = self._planner.create_plan(query, depth)

        self._monitor.log(f"Plan summary: {planner_result.plan.summary}")
        self._monitor.log(f"Subtasks: {len(planner_result.plan.subtasks)}")
        self._monitor.log(f"Execution groups: {len(planner_result.plan.execution_order)}")

        for i, group in enumerate(planner_result.plan.execution_order):
            self._monitor.log(f"  Group {i + 1}: {group}")

        self._monitor.record_reasoning_summary(
            stage="planning",
            summary=planner_result.reasoning,
            agent_id="planner",
        )

        return planner_result

    async def _initialize_agents(self, depth: ResearchDepth) -> None:
        """Initialize agents for task execution."""
        self._monitor.section("Agent Initialization")
        research_settings = self._config.research.model_dump(mode="python")

        # Create agents with config
        # SourceCollectorAgent handles its own provider initialization
        self._agents = {
            "source_collector": SourceCollectorAgent(
                config=self._config,
                monitor=self._monitor,
            ),
            "analyzer": AnalyzerAgent(
                research_settings,
                monitor=self._monitor,
                llm_router=self._llm_router,
                prompt_registry=self._prompt_registry,
            ),
            "validator": ValidatorAgent({"config": self._config.model_dump()}),
            "reporter": ReporterAgent({"config": self._config.model_dump()}),
        }

        # Initialize dispatcher
        self._dispatcher = TaskDispatcher(
            monitor=self._monitor,
            agents=self._agents,
        )

        # Register task handlers
        self._dispatcher.register_handler("search", self._handle_search_task)
        self._dispatcher.register_handler("analyze", self._handle_analyze_task)
        self._dispatcher.register_handler("validate", self._handle_validate_task)
        self._dispatcher.register_handler("synthesize", self._handle_synthesize_task)

        self._monitor.log(f"Initialized {len(self._agents)} agents")

    async def _execute_plan(
        self,
        plan: ResearchPlan,
        cancellation_check: Callable[[], None] | None = None,
        initial_results: dict[str, TaskExecutionResult] | None = None,
        group_completed_callback: (
            Callable[[dict[str, TaskExecutionResult]], Any] | None
        ) = None,
    ) -> dict[str, TaskExecutionResult]:
        """Execute the research plan."""
        if not self._dispatcher:
            raise PlannerOrchestratorError("Dispatcher not initialized")

        return await self._dispatcher.dispatch_plan(
            plan=plan,
            cancellation_check=cancellation_check,
            initial_results=initial_results,
            group_completed_callback=group_completed_callback,
        )

    async def _handle_search_task(
        self,
        *,
        task: Any,
        plan: ResearchPlan,
        dependency_outputs: dict[str, Any],
        cancellation_check: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        """Handle a search task."""
        from cc_deep_research.models import QueryFamily

        collector = self._agents.get("source_collector")
        if not collector:
            raise PlannerOrchestratorError("Source collector not initialized")

        queries = task.query_variations or [task.title]
        query_families = [
            QueryFamily(query=q, family=task.id, intent_tags=["planner"])
            for q in queries
        ]

        depth = plan.depth or ResearchDepth.STANDARD
        sources = await collector.collect_sources(
            query_families=query_families,
            depth=depth,
        )

        return {
            "sources": sources,
            "findings": [],
        }

    async def _handle_analyze_task(
        self,
        *,
        task: Any,
        plan: ResearchPlan,
        dependency_outputs: dict[str, Any],
        cancellation_check: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        """Handle an analysis task."""
        analyzer = self._agents.get("analyzer")
        if not analyzer:
            raise PlannerOrchestratorError("Analyzer not initialized")

        # Gather sources from search dependencies
        all_sources: list[SearchResultItem] = []
        for dep_id in task.dependencies:
            if dep_id in dependency_outputs:
                dep_sources = dependency_outputs[dep_id].get("sources", [])
                all_sources.extend(dep_sources)

        query = task.inputs.get("query", plan.query)
        analysis = await asyncio.to_thread(
            analyzer.analyze_sources,
            sources=all_sources,
            query=query,
        )

        # Handle both dict and AnalysisResult
        if isinstance(analysis, AnalysisResult):
            findings = [str(f) for f in analysis.key_findings[:5]]
        else:
            findings = analysis.get("key_findings", [])[:5] if isinstance(analysis, dict) else []

        return {
            "sources": all_sources,
            "findings": findings,
            "analysis": analysis,
        }

    async def _handle_validate_task(
        self,
        *,
        task: Any,
        plan: ResearchPlan,
        dependency_outputs: dict[str, Any],
        cancellation_check: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        """Handle a validation task."""
        validator = self._agents.get("validator")
        if not validator:
            raise PlannerOrchestratorError("Validator not initialized")

        # Gather sources and analysis from dependencies
        all_sources: list[SearchResultItem] = []
        analysis = None

        for dep_id in task.dependencies:
            if dep_id in dependency_outputs:
                dep_output = dependency_outputs[dep_id]
                all_sources.extend(dep_output.get("sources", []))
                if dep_output.get("analysis"):
                    analysis = dep_output["analysis"]

        query = task.inputs.get("query", plan.query)
        depth = plan.depth or ResearchDepth.STANDARD

        validation = await validator.validate(
            query=query,
            depth=depth,
            sources=all_sources,
            analysis=analysis,
        )

        # Handle both dict and ValidationResult
        if isinstance(validation, ValidationResult):
            issues = validation.issues
        else:
            issues = validation.get("issues", []) if isinstance(validation, dict) else []

        return {
            "sources": all_sources,
            "findings": issues,
            "validation": validation,
        }

    async def _handle_synthesize_task(
        self,
        *,
        task: Any,
        plan: ResearchPlan,
        dependency_outputs: dict[str, Any],
        cancellation_check: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        """Handle a synthesis task."""
        reporter = self._agents.get("reporter")
        if not reporter:
            raise PlannerOrchestratorError("Reporter not initialized")

        # Gather all sources and findings from dependencies
        all_sources: list[SearchResultItem] = []
        all_findings: list[str] = []
        analysis = None
        validation = None

        for dep_id in task.dependencies:
            if dep_id in dependency_outputs:
                dep_output = dependency_outputs[dep_id]
                all_sources.extend(dep_output.get("sources", []))
                all_findings.extend(dep_output.get("findings", []))
                if dep_output.get("analysis"):
                    analysis = dep_output["analysis"]
                if dep_output.get("validation"):
                    validation = dep_output["validation"]

        # Deduplicate sources
        seen_urls = set()
        unique_sources = []
        for source in all_sources:
            url = getattr(source, "url", None) or (source.get("url") if isinstance(source, dict) else None)
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_sources.append(source)
            elif not url:
                unique_sources.append(source)

        query = task.inputs.get("query", plan.query)

        # Generate report
        report = await reporter.generate_report(
            sources=unique_sources,
            query=query,
            analysis=analysis,
            validation=validation,
        )

        return {
            "sources": unique_sources,
            "findings": all_findings[:10],
            "report": report,
        }

    def _synthesize_results(
        self,
        plan: ResearchPlan,
        task_results: dict[str, Any],
    ) -> PlanSynthesis:
        """Synthesize results from all subtasks."""
        if not self._dispatcher:
            raise PlannerOrchestratorError("Dispatcher not initialized")

        return self._dispatcher.synthesize_results(plan, task_results)

    def _build_session(
        self,
        *,
        session_id: str,
        query: str,
        depth: ResearchDepth,
        plan: ResearchPlan,
        synthesis: PlanSynthesis,
        planner_result: PlannerResult,
        started_at: datetime,
        min_sources: int | None,
    ) -> ResearchSession:
        """Build the research session from results."""
        # Create a mock strategy result for compatibility
        strategy = StrategyResult(
            query=query,
            complexity=planner_result.complexity_assessment,
            depth=depth,
            profile=planner_result.plan.subtasks[0].inputs if plan.subtasks else {},
            strategy={"tasks": [t.task_type for t in plan.subtasks]},
        )

        # Create analysis result from synthesis
        analysis = AnalysisResult(
            key_findings=synthesis.key_findings,
            themes=synthesis.themes,
            gaps=synthesis.gaps,
            source_count=len(synthesis.all_sources),
            analysis_method="planner_workflow",
        )

        # Create validation result
        validation = ValidationResult(
            is_valid=synthesis.overall_quality_score >= 0.5,
            issues=synthesis.gaps,
            recommendations=synthesis.recommendations,
            quality_score=synthesis.overall_quality_score,
        )

        # Build provider metadata
        provider_status = "ready" if self._provider_metadata.get("available") else "unavailable"
        if self._provider_metadata.get("warnings"):
            provider_status = "degraded"

        # Calculate execution time
        execution_time = (datetime.utcnow() - started_at).total_seconds()

        # Build the unified metadata contract matching staged workflow
        strategy_dict = {
            "query": query,
            "complexity": planner_result.complexity_assessment,
            "depth": depth.value if hasattr(depth, 'value') else str(depth),
            "profile": planner_result.plan.subtasks[0].inputs if plan.subtasks else {},
            "strategy": {"tasks": [t.task_type for t in plan.subtasks]},
        }
        analysis_dict = {
            "key_findings": synthesis.key_findings,
            "themes": synthesis.themes,
            "gaps": synthesis.gaps,
            "source_count": len(synthesis.all_sources),
            "analysis_method": "planner_workflow",
        }
        validation_dict = {
            "is_valid": synthesis.overall_quality_score >= 0.5,
            "issues": synthesis.gaps,
            "recommendations": synthesis.recommendations,
            "quality_score": synthesis.overall_quality_score,
        }

        metadata: dict[str, Any] = {
            "strategy": strategy_dict,
            "analysis": analysis_dict,
            "validation": validation_dict,
            "iteration_history": [
                {"iteration": 0, "source_count": len(synthesis.all_sources)}
            ],
            "providers": {
                "configured": list(self._config.search.providers) if hasattr(self._config, 'search') else [],
                "available": self._provider_metadata.get("available", []),
                "warnings": self._provider_metadata.get("warnings", []),
                "status": provider_status,
            },
            "execution": {
                "parallel_requested": False,
                "parallel_used": False,
                "degraded": bool(self._execution_degradations),
                "degraded_reasons": self._execution_degradations,
            },
            "deep_analysis": {
                "requested": False,
                "completed": False,
                "status": "not_requested",
                "reason": None,
            },
            "llm_routes": self._llm_routes,
            "prompts": {
                "overrides_applied": bool(self._prompt_registry and hasattr(self._prompt_registry, 'has_overrides') and self._prompt_registry.has_overrides()),
                "effective_overrides": self._prompt_registry.get_effective_overrides() if self._prompt_registry and hasattr(self._prompt_registry, 'get_effective_overrides') else {},
                "default_prompts_used": [],
            },
            # Planner-specific metadata nested under planner key
            "planner": {
                "workflow": "planner",
                "plan_id": plan.plan_id,
                "plan_summary": plan.summary,
                "total_subtasks": len(plan.subtasks),
                "completed_subtasks": synthesis.completed_subtasks,
                "failed_subtasks": synthesis.failed_subtasks,
                "complexity": planner_result.complexity_assessment,
                "estimated_time_minutes": planner_result.estimated_time_minutes,
                "planner_confidence": planner_result.confidence,
                "iteration_policy": {
                    "mode": "single_plan",
                    "iterative_search_supported": False,
                    "reason": "Planner beta executes one planned task graph and does not yet schedule validation-driven follow-up loops.",
                },
            },
        }

        return ResearchSession(
            session_id=session_id,
            query=query,
            depth=depth,
            sources=synthesis.all_sources,
            analysis=analysis,
            validation=validation,
            strategy=strategy,
            total_sources=len(synthesis.all_sources),
            execution_time_seconds=execution_time,
            metadata=metadata,
            started_at=started_at,
            completed_at=datetime.utcnow(),
        )

    def _notify_phase(
        self,
        phase_hook: Callable[[str, str], None] | None,
        phase_key: str,
        description: str,
    ) -> None:
        """Notify about phase progress."""
        if phase_hook:
            phase_hook(phase_key, description)
        self._monitor.log(f"[{phase_key}] {description}")

    async def _cleanup(self) -> None:
        """Clean up resources."""
        self._agents.clear()
        self._dispatcher = None


class PlannerOrchestratorError(Exception):
    """Exception raised when planner orchestrator execution fails."""

    def __init__(
        self,
        message: str,
        query: str | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.query = query
        self.original_error = original_error


__all__ = [
    "PlannerResearchOrchestrator",
    "PlannerOrchestratorError",
]
