"""Base class for per-stage orchestrators."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cc_deep_research.config import Config

if TYPE_CHECKING:
    from cc_deep_research.content_gen.models import PipelineContext


class BaseStageOrchestrator:
    """Base class for per-stage orchestrators.

    Provides common functionality for stage-specific orchestrators,
    including agent management and configuration access.
    """

    def __init__(self, config: Config) -> None:
        """Initialize the stage orchestrator.

        Args:
            config: Application configuration.
        """
        self._config = config
        self._agents: dict[str, object] = {}

    def _get_agent(self, name: str) -> object:
        """Get or create a cached agent instance."""
        if name not in self._agents:
            self._agents[name] = self._create_agent(name)
        return self._agents[name]

    def _create_agent(self, name: str) -> object:
        """Create a new agent instance. Override in subclasses for custom agent creation."""
        raise NotImplementedError

    async def run_with_context(self, ctx: "PipelineContext") -> "PipelineContext":
        """Run this stage with full pipeline context.

        Override in subclasses to integrate with the content-gen pipeline.
        The default implementation raises NotImplementedError.

        Args:
            ctx: The current pipeline context.

        Returns:
            Updated pipeline context after running the stage.
        """
        raise NotImplementedError(
            f"Stage {self.__class__.__name__} does not implement run_with_context. "
            "Use stage-specific run methods for standalone operation."
        )
