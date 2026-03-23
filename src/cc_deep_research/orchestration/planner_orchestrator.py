"""Planner-based research orchestrator for the hierarchical workflow."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

from cc_deep_research.agents import (
    AnalyzerAgent,
    PlannerAgent,
    ReporterAgent,
    SourceCollectorAgent,
    ValidatorAgent,
)
from cc_deep_research.config import Config
from cc_deep_research.models import (
    AnalysisResult,
    PlannerResult,
    PlanSynthesis,
    ResearchDepth,
    ResearchPlan,
    ResearchSession,
    SearchResultItem,
    StrategyResult,
    ValidationResult,
)
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.orchestration.session_builder import SessionBuilder
from cc_deep_research.orchestration.task_dispatcher import TaskDispatcher


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
    ) -> None:
        """Initialize the planner orchestrator.

        Args:
            config: Application configuration.
            monitor: Optional research monitor for progress tracking.
        """
        self._config = config
        self._monitor = monitor or ResearchMonitor(enabled=False)
        self._planner = PlannerAgent(config.model_dump())
        self._dispatcher: TaskDispatcher | None = None
        self._agents: dict[str, Any] = {}
        self._team: LocalResearchTeam | None = None
        self._session_builder = SessionBuilder()

    async def execute_research(
        self,
        query: str,
        depth: ResearchDepth,
        min_sources: int | None = None,
        phase_hook: Callable[[str, str], None] | None = None,
        cancellation_check: Callable[[], None] | None = None,
        on_session_started: Callable[[str], None] | None = None,
    ) -> ResearchSession:
        """Execute research using the planner workflow.

        Args:
            query: Research query string.
            depth: Research depth mode (quick/standard/deep).
            min_sources: Minimum number of sources (optional).
            phase_hook: Optional callback for phase progress updates.
            cancellation_check: Optional callback to check for cancellation.
            on_session_started: Optional callback when session starts.

        Returns:
            ResearchSession with complete research results.

        Raises:
            PlannerOrchestratorError: If research execution fails.
        """
        start_time = datetime.utcnow()

        # Initialize session
        session_id = self._initialize_session(
            query=query,
            depth=depth,
            on_session_started=on_session_started,
        )

        try:
            # Phase 1: Planning
            self._notify_phase(phase_hook, "planning", "Creating research plan")
            planner_result = await self._create_plan(query, depth)
            plan = planner_result.plan

            self._monitor.log(f"Plan created with {len(plan.subtasks)} subtasks")
            self._monitor.log(f"Complexity: {planner_result.complexity_assessment}")
            self._monitor.log(f"Estimated time: {planner_result.estimated_time_minutes} minutes")

            # Phase 2: Initialize agents and dispatcher
            self._notify_phase(phase_hook, "init", "Initializing agents")
            await self._initialize_agents(depth)

            # Phase 3: Execute plan
            self._notify_phase(phase_hook, "execution", "Executing research plan")
            task_results = await self._execute_plan(
                plan,
                cancellation_check=cancellation_check,
            )

            # Phase 4: Synthesize results
            self._notify_phase(phase_hook, "synthesis", "Synthesizing results")
            synthesis = self._synthesize_results(plan, task_results)

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

            self._monitor.log(f"Research complete: {len(synthesis.all_sources)} sources, {len(synthesis.key_findings)} findings")

            return session

        except Exception as exc:
            self._monitor.log(f"Research failed: {exc}")
            raise PlannerOrchestratorError(
                f"Research execution failed: {exc}",
                query=query,
                original_error=exc,
            ) from exc

        finally:
            await self._cleanup()

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

        # Create agents with config
        # SourceCollectorAgent handles its own provider initialization
        self._agents = {
            "source_collector": SourceCollectorAgent(
                config=self._config,
                monitor=self._monitor,
            ),
            "analyzer": AnalyzerAgent({"config": self._config.model_dump()}),
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
    ) -> dict[str, Any]:
        """Execute the research plan."""
        if not self._dispatcher:
            raise PlannerOrchestratorError("Dispatcher not initialized")

        return await self._dispatcher.dispatch_plan(
            plan=plan,
            cancellation_check=cancellation_check,
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
        analysis = await analyzer.analyze(
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

        # Build metadata
        metadata = {
            "workflow": "planner",
            "plan_id": plan.plan_id,
            "plan_summary": plan.summary,
            "total_subtasks": len(plan.subtasks),
            "completed_subtasks": synthesis.completed_subtasks,
            "failed_subtasks": synthesis.failed_subtasks,
            "complexity": planner_result.complexity_assessment,
            "estimated_time_minutes": planner_result.estimated_time_minutes,
            "planner_confidence": planner_result.confidence,
        }

        # Calculate execution time
        execution_time = (datetime.utcnow() - started_at).total_seconds()

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
