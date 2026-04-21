"""Content generation pipeline coordinator.

This module provides ContentGenPipeline, which coordinates per-stage
orchestrators to execute the full content generation pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from cc_deep_research.config import Config

if TYPE_CHECKING:
    from cc_deep_research.content_gen.models import PipelineContext


class ContentGenPipeline:
    """Coordinator for the content generation pipeline.

    Orchestrates per-stage orchestrators to execute the full pipeline.
    Each stage is handled by a dedicated stage orchestrator.

    This class provides the main entry point for running the full
    content generation pipeline, coordinating between:
    - BacklogStageOrchestrator (build_backlog, score_ideas)
    - AngleStageOrchestrator (generate_angles)
    - ResearchStageOrchestrator (build_research_pack)
    - ArgumentMapStageOrchestrator (build_argument_map)
    - ScriptingStageOrchestrator (run_scripting)
    - VisualStageOrchestrator (visual_translation)
    - ProductionStageOrchestrator (production_brief)
    - PackagingStageOrchestrator (packaging)
    - QCStageOrchestrator (human_qc)
    - PublishStageOrchestrator (publish)
    """

    def __init__(self, config: Config) -> None:
        """Initialize the pipeline coordinator.

        Args:
            config: Application configuration.
        """
        self._config = config
        self._stage_orchestrators: dict[str, Any] = {}

    def _get_stage(self, name: str) -> Any:
        """Get or create a stage orchestrator by name."""
        if name not in self._stage_orchestrators:
            self._stage_orchestrators[name] = self._create_stage(name)
        return self._stage_orchestrators[name]

    def _create_stage(self, name: str) -> Any:
        """Create a stage orchestrator by name."""
        from cc_deep_research.content_gen.stages.backlog import BacklogStageOrchestrator
        from cc_deep_research.content_gen.stages.angle import AngleStageOrchestrator
        from cc_deep_research.content_gen.stages.research import ResearchStageOrchestrator
        from cc_deep_research.content_gen.stages.argument_map import ArgumentMapStageOrchestrator
        from cc_deep_research.content_gen.stages.scripting import ScriptingStageOrchestrator
        from cc_deep_research.content_gen.stages.visual import VisualStageOrchestrator
        from cc_deep_research.content_gen.stages.production import ProductionStageOrchestrator
        from cc_deep_research.content_gen.stages.packaging import PackagingStageOrchestrator
        from cc_deep_research.content_gen.stages.qc import QCStageOrchestrator
        from cc_deep_research.content_gen.stages.publish import PublishStageOrchestrator

        stages: dict[str, type] = {
            "backlog": BacklogStageOrchestrator,
            "angle": AngleStageOrchestrator,
            "research": ResearchStageOrchestrator,
            "argument_map": ArgumentMapStageOrchestrator,
            "scripting": ScriptingStageOrchestrator,
            "visual": VisualStageOrchestrator,
            "production": ProductionStageOrchestrator,
            "packaging": PackagingStageOrchestrator,
            "qc": QCStageOrchestrator,
            "publish": PublishStageOrchestrator,
        }

        orchestrator_class = stages.get(name)
        if orchestrator_class is None:
            raise ValueError(f"Unknown stage: {name}")
        return orchestrator_class(self._config)

    async def run_stage(
        self,
        stage_name: str,
        ctx: PipelineContext,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> PipelineContext:
        """Run a single pipeline stage.

        Args:
            stage_name: Name of the stage to run.
            ctx: Pipeline context.
            progress_callback: Optional callback for progress updates.

        Returns:
            Updated pipeline context after running the stage.
        """
        # Delegate to the main orchestrator for stage execution
        # (stage orchestration logic lives in ContentGenOrchestrator)
        from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

        orch = ContentGenOrchestrator(self._config)
        return await orch._run_stage(
            ctx.current_stage,
            ctx,
            progress_callback,
        )

    # Stage-specific run methods that delegate to stage orchestrators
    async def run_backlog(self, theme: str, *, count: int = 20) -> Any:
        """Run the backlog building stage."""
        stage = self._get_stage("backlog")
        return await stage.run_backlog(theme, count=count)

    async def run_scoring(self, items: list) -> Any:
        """Run the idea scoring stage."""
        stage = self._get_stage("backlog")
        return await stage.run_scoring(items)

    async def run_angle(self, item: Any) -> Any:
        """Run the angle generation stage."""
        stage = self._get_stage("angle")
        return await stage.run_angle(item)

    async def run_research(self, item: Any, angle: Any) -> Any:
        """Run the research pack stage."""
        stage = self._get_stage("research")
        return await stage.run_research(item, angle)

    async def run_argument_map(self, item: Any, angle: Any, research_pack: Any) -> Any:
        """Run the argument map stage."""
        stage = self._get_stage("argument_map")
        return await stage.run_argument_map(item, angle, research_pack)

    async def run_scripting(self, idea: Any, **kwargs: Any) -> Any:
        """Run the scripting stage."""
        stage = self._get_stage("scripting")
        return await stage.run_scripting(idea, **kwargs)

    async def run_visual(self, scripting_ctx: Any, **kwargs: Any) -> Any:
        """Run the visual translation stage."""
        stage = self._get_stage("visual")
        return await stage.run_visual(scripting_ctx, **kwargs)

    async def run_production(self, visual_plan: Any) -> Any:
        """Run the production brief stage."""
        stage = self._get_stage("production")
        return await stage.run_production(visual_plan)

    async def run_packaging(self, script: Any, angle: Any, **kwargs: Any) -> Any:
        """Run the packaging stage."""
        stage = self._get_stage("packaging")
        return await stage.run_packaging(script, angle, **kwargs)

    async def run_qc(self, script: str, **kwargs: Any) -> Any:
        """Run the QC stage."""
        stage = self._get_stage("qc")
        return await stage.run_qc(script=script, **kwargs)

    async def run_publish(self, packaging: Any, **kwargs: Any) -> Any:
        """Run the publish stage."""
        stage = self._get_stage("publish")
        return await stage.run_publish(packaging, **kwargs)
