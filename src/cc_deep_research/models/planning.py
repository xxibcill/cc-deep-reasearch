"""Planning-domain models for the planner-based workflow."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .search import ResearchDepth


class ResearchSubtask(BaseModel):
    """A discrete research task to be executed by a specialized agent."""

    id: str = Field(description="Unique identifier for this subtask")
    title: str = Field(description="Brief title describing the subtask")
    description: str = Field(description="Detailed description of what this subtask should accomplish")
    task_type: str = Field(
        description="Type of task: search, analyze, validate, synthesize",
        pattern="^(search|analyze|validate|synthesize)$",
    )
    assigned_agent: str | None = Field(
        default=None,
        description="Agent assigned to execute this subtask",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="IDs of prerequisite subtasks that must complete first",
    )
    priority: int = Field(
        default=1,
        ge=1,
        le=5,
        description="Priority level (1=highest, 5=lowest)",
    )
    status: str = Field(
        default="pending",
        description="Current status: pending, in_progress, completed, failed, skipped",
        pattern="^(pending|in_progress|completed|failed|skipped)$",
    )
    inputs: dict[str, Any] = Field(
        default_factory=dict,
        description="Input parameters for this subtask",
    )
    outputs: dict[str, Any] = Field(
        default_factory=dict,
        description="Outputs produced by this subtask",
    )
    estimated_sources: int = Field(
        default=5,
        ge=0,
        description="Estimated number of sources this subtask will produce/require",
    )
    query_variations: list[str] = Field(
        default_factory=list,
        description="Search query variations for this subtask (if task_type is 'search')",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if subtask failed",
    )
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Number of times this subtask has been retried",
    )
    max_retries: int = Field(
        default=2,
        ge=0,
        description="Maximum number of retries allowed",
    )


class ResearchPlan(BaseModel):
    """A complete research plan with subtasks and execution strategy."""

    plan_id: str = Field(description="Unique identifier for this plan")
    query: str = Field(description="Original research query")
    summary: str = Field(description="Brief summary of the research approach")
    subtasks: list[ResearchSubtask] = Field(
        default_factory=list,
        description="List of subtasks to execute",
    )
    execution_order: list[list[str]] = Field(
        default_factory=list,
        description="Groups of subtask IDs that can run in parallel, in execution order",
    )
    success_criteria: list[str] = Field(
        default_factory=list,
        description="Criteria that determine if the research is successful",
    )
    fallback_strategies: list[str] = Field(
        default_factory=list,
        description="Fallback approaches if primary strategy fails",
    )
    estimated_total_sources: int = Field(
        default=20,
        ge=0,
        description="Estimated total number of sources to collect",
    )
    depth: ResearchDepth | None = Field(
        default=None,
        description="Research depth mode for this plan",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this plan was created",
    )

    def get_subtask(self, task_id: str) -> ResearchSubtask | None:
        """Get a subtask by its ID."""
        for task in self.subtasks:
            if task.id == task_id:
                return task
        return None

    def update_subtask_status(self, task_id: str, status: str) -> None:
        """Update the status of a subtask."""
        task = self.get_subtask(task_id)
        if task:
            task.status = status

    def get_pending_subtasks(self) -> list[ResearchSubtask]:
        """Get all pending subtasks."""
        return [t for t in self.subtasks if t.status == "pending"]

    def get_ready_subtasks(self) -> list[ResearchSubtask]:
        """Get subtasks that are ready to execute (pending with all dependencies met)."""
        completed_ids = {t.id for t in self.subtasks if t.status == "completed"}
        ready = []
        for task in self.subtasks:
            if task.status != "pending":
                continue
            if all(dep_id in completed_ids for dep_id in task.dependencies):
                ready.append(task)
        return ready

    def get_current_execution_group(self) -> list[str] | None:
        """Get the current group of tasks that should be executing."""
        for group in self.execution_order:
            for tid in group:
                subtask = self.get_subtask(tid)
                if subtask and subtask.status in ("pending", "in_progress"):
                    return group
        return None

    def is_complete(self) -> bool:
        """Check if all subtasks are completed or skipped."""
        return all(t.status in ("completed", "skipped") for t in self.subtasks)

    def has_failures(self) -> bool:
        """Check if any critical subtasks have failed."""
        return any(t.status == "failed" for t in self.subtasks)


class PlannerResult(BaseModel):
    """Result from the Planner Agent."""

    plan: ResearchPlan = Field(description="The generated research plan")
    reasoning: str = Field(description="Explanation of why this plan was chosen")
    alternative_approaches: list[str] = Field(
        default_factory=list,
        description="Alternative approaches that were considered",
    )
    complexity_assessment: str = Field(
        default="moderate",
        description="Assessment of query complexity: simple, moderate, complex",
        pattern="^(simple|moderate|complex)$",
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence level in the plan (0.0 to 1.0)",
    )
    estimated_time_minutes: int = Field(
        default=5,
        ge=1,
        description="Estimated time to complete the plan in minutes",
    )


class PlannerIterationDecision(BaseModel):
    """Planner-owned decision for whether the research loop should continue."""

    should_continue: bool = Field(
        description="Whether the workflow should execute another research iteration",
    )
    reason_code: str = Field(
        description="Stable label describing why the planner made this decision",
    )
    stop_reason: str | None = Field(
        default=None,
        description="Normalized terminal stop reason when the loop should stop",
    )
    rationale: str = Field(
        default="",
        description="Human-readable explanation of the planner decision",
    )
    current_hypothesis: str = Field(
        default="",
        description="Planner's current working hypothesis after reviewing the evidence",
    )
    missing_information: list[str] = Field(
        default_factory=list,
        description="Open evidence gaps the planner still wants to resolve",
    )
    next_queries: list[str] = Field(
        default_factory=list,
        description="Planner-selected follow-up queries for the next loop iteration",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence in the planner's stop/continue decision",
    )


class TaskExecutionResult(BaseModel):
    """Result from executing a single subtask."""

    task_id: str = Field(description="ID of the executed subtask")
    success: bool = Field(description="Whether the subtask completed successfully")
    outputs: dict[str, Any] = Field(
        default_factory=dict,
        description="Outputs produced by this subtask",
    )
    sources: list[Any] = Field(
        default_factory=list,
        description="Sources collected/produced by this subtask",
    )
    findings: list[str] = Field(
        default_factory=list,
        description="Key findings from this subtask",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if subtask failed",
    )
    execution_time_seconds: float = Field(
        default=0.0,
        ge=0.0,
        description="Time taken to execute this subtask",
    )
    should_retry: bool = Field(
        default=False,
        description="Whether this subtask should be retried",
    )


class PlanSynthesis(BaseModel):
    """Synthesized results from all subtasks in a plan."""

    plan_id: str = Field(description="ID of the research plan")
    query: str = Field(description="Original research query")
    task_results: dict[str, TaskExecutionResult] = Field(
        default_factory=dict,
        description="Results from each subtask, keyed by task ID",
    )
    all_sources: list[Any] = Field(
        default_factory=list,
        description="All sources collected across all subtasks",
    )
    key_findings: list[str] = Field(
        default_factory=list,
        description="Synthesized key findings from all subtasks",
    )
    themes: list[str] = Field(
        default_factory=list,
        description="Common themes identified across subtasks",
    )
    gaps: list[str] = Field(
        default_factory=list,
        description="Remaining gaps in the research",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Recommendations based on the research",
    )
    overall_quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall quality score of the research",
    )
    completed_subtasks: int = Field(
        default=0,
        ge=0,
        description="Number of successfully completed subtasks",
    )
    failed_subtasks: int = Field(
        default=0,
        ge=0,
        description="Number of failed subtasks",
    )


__all__ = [
    "ResearchSubtask",
    "ResearchPlan",
    "PlannerIterationDecision",
    "PlannerResult",
    "TaskExecutionResult",
    "PlanSynthesis",
]
