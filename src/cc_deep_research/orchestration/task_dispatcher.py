"""Task dispatcher for executing research subtasks."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

from cc_deep_research.models import (
    PlanSynthesis,
    ResearchPlan,
    ResearchSubtask,
    TaskExecutionResult,
)
from cc_deep_research.monitoring import ResearchMonitor

from .resilience import decide_subtask_retry


class TaskDispatcher:
    """Dispatches subtasks to appropriate agents and tracks progress.

    The dispatcher is responsible for:
    - Executing subtasks in the correct order based on dependencies
    - Running independent subtasks in parallel
    - Tracking results and status of each subtask
    - Handling failures and retries
    """

    def __init__(
        self,
        monitor: ResearchMonitor,
        agents: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the task dispatcher.

        Args:
            monitor: Research monitor for logging.
            agents: Optional dictionary of agent instances keyed by agent type.
        """
        self._monitor = monitor
        self._agents = agents or {}
        self._task_results: dict[str, TaskExecutionResult] = {}
        self._execution_handlers: dict[str, Callable[..., Awaitable[Any]]] = {}

    def register_agent(self, agent_type: str, agent: Any) -> None:
        """Register an agent for a specific type.

        Args:
            agent_type: Type identifier for the agent.
            agent: Agent instance.
        """
        self._agents[agent_type] = agent

    def register_handler(
        self,
        task_type: str,
        handler: Callable[..., Awaitable[Any]],
    ) -> None:
        """Register a custom handler for a task type.

        Args:
            task_type: Type of task (search, analyze, validate, synthesize).
            handler: Async function to handle tasks of this type.
        """
        self._execution_handlers[task_type] = handler

    async def dispatch_plan(
        self,
        plan: ResearchPlan,
        cancellation_check: Callable[[], None] | None = None,
    ) -> dict[str, TaskExecutionResult]:
        """Execute a research plan by dispatching subtasks.

        Args:
            plan: The research plan to execute.
            cancellation_check: Optional callback to check for cancellation.

        Returns:
            Dictionary mapping task IDs to their execution results.
        """
        self._monitor.section("Task Dispatch")
        self._monitor.log(f"Plan ID: {plan.plan_id}")
        self._monitor.log(f"Total subtasks: {len(plan.subtasks)}")
        self._monitor.log(f"Execution groups: {len(plan.execution_order)}")

        self._task_results = {}

        for group_index, task_group in enumerate(plan.execution_order):
            self._check_cancellation(cancellation_check)

            self._monitor.log(f"\nExecuting group {group_index + 1}/{len(plan.execution_order)}: {task_group}")

            # Execute tasks in this group in parallel
            tasks = [
                self._execute_subtask(plan, task_id, cancellation_check)
                for task_id in task_group
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for task_id, result in zip(task_group, results, strict=True):
                if isinstance(result, Exception):
                    self._monitor.log(f"  Task {task_id} failed: {result}")
                    self._task_results[task_id] = TaskExecutionResult(
                        task_id=task_id,
                        success=False,
                        error_message=str(result),
                    )
                    plan.update_subtask_status(task_id, "failed")
                else:
                    self._task_results[task_id] = result
                    if result.success:
                        plan.update_subtask_status(task_id, "completed")
                        self._monitor.log(f"  Task {task_id} completed")
                    else:
                        plan.update_subtask_status(task_id, "failed")
                        self._monitor.log(f"  Task {task_id} failed: {result.error_message}")

            # Check if any critical failures should stop execution
            if self._should_abort(plan, task_group):
                self._monitor.log("Aborting plan execution due to critical failures")
                self._mark_remaining_as_skipped(plan, task_group)
                break

        return self._task_results

    async def _execute_subtask(
        self,
        plan: ResearchPlan,
        task_id: str,
        cancellation_check: Callable[[], None] | None = None,
    ) -> TaskExecutionResult:
        """Execute a single subtask using the assigned agent.

        Args:
            plan: The research plan.
            task_id: ID of the subtask to execute.
            cancellation_check: Optional cancellation check.

        Returns:
            TaskExecutionResult with the outcome.
        """
        task = plan.get_subtask(task_id)
        if not task:
            return TaskExecutionResult(
                task_id=task_id,
                success=False,
                error_message=f"Task {task_id} not found in plan",
            )

        plan.update_subtask_status(task_id, "in_progress")
        start_time = time.time()
        attempt = 1
        while True:
            task.retry_count = max(0, attempt - 1)
            try:
                dependency_outputs = self._gather_dependency_outputs(task, plan)
                handler = self._get_handler(task.task_type)
                if handler:
                    result = await handler(
                        task=task,
                        plan=plan,
                        dependency_outputs=dependency_outputs,
                        cancellation_check=cancellation_check,
                    )
                else:
                    result = await self._default_execute(
                        task,
                        plan,
                        dependency_outputs,
                        cancellation_check,
                    )

                execution_time = time.time() - start_time
                return TaskExecutionResult(
                    task_id=task_id,
                    success=True,
                    outputs=result if isinstance(result, dict) else {"result": result},
                    sources=result.get("sources", []) if isinstance(result, dict) else [],
                    findings=result.get("findings", []) if isinstance(result, dict) else [],
                    execution_time_seconds=execution_time,
                )
            except Exception as e:
                retry_decision = decide_subtask_retry(
                    task=task,
                    attempt=attempt,
                    error=e,
                )
                self._monitor.record_retry_decision(
                    task_id=task.id,
                    attempt=retry_decision.attempt,
                    max_attempts=retry_decision.max_attempts,
                    should_retry=retry_decision.should_retry,
                    reason_code=retry_decision.reason_code,
                    actor_id=task.assigned_agent,
                    task_type=task.task_type,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                if retry_decision.should_retry:
                    self._monitor.log(
                        f"  Retrying task {task_id} "
                        f"({attempt}/{retry_decision.max_attempts}) after {type(e).__name__}: {e}"
                    )
                    attempt += 1
                    continue

                execution_time = time.time() - start_time
                return TaskExecutionResult(
                    task_id=task_id,
                    success=False,
                    error_message=str(e),
                    execution_time_seconds=execution_time,
                    should_retry=False,
                )

    def _get_handler(self, task_type: str) -> Callable[..., Awaitable[Any]] | None:
        """Get the handler for a task type."""
        return self._execution_handlers.get(task_type)

    async def _default_execute(
        self,
        task: ResearchSubtask,
        plan: ResearchPlan,
        dependency_outputs: dict[str, Any],
        cancellation_check: Callable[[], None] | None = None,
    ) -> Any:
        """Default execution using registered agents.

        Args:
            task: The subtask to execute.
            plan: The research plan.
            dependency_outputs: Outputs from dependency tasks.
            cancellation_check: Optional cancellation check.

        Returns:
            Execution result.
        """
        if not task.assigned_agent:
            raise ValueError(f"Task {task.id} has no assigned agent")

        agent = self._agents.get(task.assigned_agent)
        if not agent:
            raise ValueError(f"No agent registered for type: {task.assigned_agent}")

        self._check_cancellation(cancellation_check)

        # Execute based on task type
        if task.task_type == "search":
            return await self._execute_search(agent, task, dependency_outputs)
        elif task.task_type == "analyze":
            return await self._execute_analyze(agent, task, dependency_outputs)
        elif task.task_type == "validate":
            return await self._execute_validate(agent, task, dependency_outputs)
        elif task.task_type == "synthesize":
            return await self._execute_synthesize(agent, task, dependency_outputs)
        else:
            raise ValueError(f"Unknown task type: {task.task_type}")

    async def _execute_search(
        self,
        agent: Any,
        task: ResearchSubtask,
        dependency_outputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a search task."""
        self._monitor.log(f"  Executing search task: {task.title}")

        # Get query variations
        queries = task.query_variations or [task.title]

        # Call the agent's search method
        # This depends on the actual agent interface
        if hasattr(agent, "collect_sources"):
            sources = await agent.collect_sources(
                query_families=[{"query": q} for q in queries],
                depth=task.inputs.get("depth"),
            )
        elif hasattr(agent, "search"):
            sources = await agent.search(queries)
        else:
            raise AttributeError(f"Agent {type(agent).__name__} has no search or collect_sources method")

        return {
            "sources": sources,
            "findings": [],
        }

    async def _execute_analyze(
        self,
        agent: Any,
        task: ResearchSubtask,
        dependency_outputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute an analysis task."""
        self._monitor.log(f"  Executing analyze task: {task.title}")

        # Gather sources from search dependencies
        all_sources = []
        for dep_id in task.dependencies:
            if dep_id in self._task_results:
                all_sources.extend(self._task_results[dep_id].sources)

        # Call the agent's analyze method
        if hasattr(agent, "analyze"):
            analysis = await agent.analyze(
                sources=all_sources,
                query=task.inputs.get("query", ""),
            )
        elif hasattr(agent, "analyze_findings"):
            analysis = await agent.analyze_findings(
                sources=all_sources,
                query=task.inputs.get("query", ""),
            )
        else:
            raise AttributeError(f"Agent {type(agent).__name__} has no analyze method")

        return {
            "sources": all_sources,
            "findings": analysis.get("key_findings", []) if isinstance(analysis, dict) else [],
            "analysis": analysis,
        }

    async def _execute_validate(
        self,
        agent: Any,
        task: ResearchSubtask,
        dependency_outputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a validation task."""
        self._monitor.log(f"  Executing validate task: {task.title}")

        # Get analysis results from dependencies
        analysis = None
        sources = []
        for dep_id in task.dependencies:
            if dep_id in self._task_results:
                result = self._task_results[dep_id]
                sources.extend(result.sources)
                if result.outputs.get("analysis"):
                    analysis = result.outputs["analysis"]

        # Call the agent's validate method
        if hasattr(agent, "validate"):
            validation = await agent.validate(
                sources=sources,
                analysis=analysis,
                query=task.inputs.get("query", ""),
            )
        else:
            raise AttributeError(f"Agent {type(agent).__name__} has no validate method")

        return {
            "sources": sources,
            "findings": validation.get("issues", []) if isinstance(validation, dict) else [],
            "validation": validation,
        }

    async def _execute_synthesize(
        self,
        agent: Any,
        task: ResearchSubtask,
        dependency_outputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a synthesis task."""
        self._monitor.log(f"  Executing synthesize task: {task.title}")

        # Gather all results from dependencies
        all_sources = []
        all_findings = []
        analysis_results = []
        validation_results = []

        for dep_id in task.dependencies:
            if dep_id in self._task_results:
                result = self._task_results[dep_id]
                all_sources.extend(result.sources)
                all_findings.extend(result.findings)
                if result.outputs.get("analysis"):
                    analysis_results.append(result.outputs["analysis"])
                if result.outputs.get("validation"):
                    validation_results.append(result.outputs["validation"])

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

        # Call the agent's synthesize/report method
        if hasattr(agent, "generate_report"):
            report = await agent.generate_report(
                sources=unique_sources,
                findings=all_findings,
                analysis=analysis_results[0] if analysis_results else None,
                query=task.inputs.get("query", ""),
            )
        elif hasattr(agent, "synthesize"):
            report = await agent.synthesize(
                sources=unique_sources,
                findings=all_findings,
                query=task.inputs.get("query", ""),
            )
        else:
            raise AttributeError(f"Agent {type(agent).__name__} has no generate_report or synthesize method")

        return {
            "sources": unique_sources,
            "findings": all_findings,
            "report": report,
        }

    def _gather_dependency_outputs(
        self,
        task: ResearchSubtask,
        plan: ResearchPlan,
    ) -> dict[str, Any]:
        """Gather outputs from all dependency tasks."""
        outputs = {}
        for dep_id in task.dependencies:
            if dep_id in self._task_results:
                outputs[dep_id] = self._task_results[dep_id].outputs
        return outputs

    def _check_cancellation(self, check: Callable[[], None] | None) -> None:
        """Check if execution should be cancelled."""
        if check:
            check()

    def _should_abort(self, plan: ResearchPlan, completed_group: list[str]) -> bool:
        """Check if execution should abort due to failures."""
        # Check if any task in the completed group failed and has dependents
        for task_id in completed_group:
            result = self._task_results.get(task_id)
            if result and not result.success:
                task = plan.get_subtask(task_id)
                if task:
                    # Check if any remaining tasks depend on this failed task
                    for remaining_task in plan.subtasks:
                        if remaining_task.status == "pending" and task_id in remaining_task.dependencies:
                            return True
        return False

    def _mark_remaining_as_skipped(self, plan: ResearchPlan, last_group: list[str]) -> None:
        """Mark all remaining tasks as skipped."""
        for task in plan.subtasks:
            if task.status == "pending":
                task.status = "skipped"

    def synthesize_results(
        self,
        plan: ResearchPlan,
        task_results: dict[str, TaskExecutionResult],
    ) -> PlanSynthesis:
        """Synthesize results from all executed subtasks.

        Args:
            plan: The research plan.
            task_results: Results from each subtask.

        Returns:
            PlanSynthesis with combined results.
        """
        all_sources: list[Any] = []
        all_findings: list[str] = []
        completed = 0
        failed = 0

        for _task_id, result in task_results.items():
            if result.success:
                completed += 1
                all_sources.extend(result.sources)
                all_findings.extend(result.findings)
            else:
                failed += 1

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

        # Calculate quality score
        quality_score = 0.0
        if plan.subtasks:
            quality_score = completed / len(plan.subtasks)

        # Extract themes from findings
        themes = self._extract_themes(all_findings)

        return PlanSynthesis(
            plan_id=plan.plan_id,
            query=plan.query,
            task_results=task_results,
            all_sources=unique_sources,
            key_findings=all_findings[:10],  # Top 10 findings
            themes=themes,
            gaps=self._identify_gaps(plan, task_results),
            recommendations=self._generate_recommendations(plan, task_results),
            overall_quality_score=quality_score,
            completed_subtasks=completed,
            failed_subtasks=failed,
        )

    def _extract_themes(self, findings: list[str]) -> list[str]:
        """Extract common themes from findings."""
        # Simple keyword extraction for themes
        if not findings:
            return []

        # Count word frequencies
        word_counts: dict[str, int] = {}
        for finding in findings:
            words = finding.lower().split()
            for word in words:
                if len(word) > 4:  # Only significant words
                    word_counts[word] = word_counts.get(word, 0) + 1

        # Get top themes
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        return [word for word, count in sorted_words[:5]]

    def _identify_gaps(
        self,
        plan: ResearchPlan,
        task_results: dict[str, TaskExecutionResult],
    ) -> list[str]:
        """Identify gaps in the research."""
        gaps = []

        # Check for failed tasks
        for task in plan.subtasks:
            if task.status == "failed":
                gaps.append(f"Failed to complete: {task.title}")

        # Check for skipped tasks
        for task in plan.subtasks:
            if task.status == "skipped":
                gaps.append(f"Skipped due to dependency failure: {task.title}")

        return gaps

    def _generate_recommendations(
        self,
        plan: ResearchPlan,
        task_results: dict[str, TaskExecutionResult],
    ) -> list[str]:
        """Generate recommendations based on research results."""
        recommendations = []

        # Check source count
        total_sources = sum(len(r.sources) for r in task_results.values())
        if total_sources < plan.estimated_total_sources:
            recommendations.append(
                f"Consider expanding search - only {total_sources} sources found "
                f"(estimated: {plan.estimated_total_sources})"
            )

        # Check for failed tasks
        failed_tasks = [t for t in plan.subtasks if t.status == "failed"]
        if failed_tasks:
            recommendations.append(
                f"Review failed tasks: {', '.join(t.title for t in failed_tasks)}"
            )

        return recommendations


__all__ = ["TaskDispatcher"]
