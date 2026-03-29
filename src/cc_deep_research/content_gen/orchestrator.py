"""Orchestrator for the content generation workflow."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from cc_deep_research.content_gen.agents.scripting import ScriptingAgent
from cc_deep_research.content_gen.models import ScriptingContext

if TYPE_CHECKING:
    from cc_deep_research.config import Config


class ContentGenOrchestrator:
    """Coordinate content generation modules.

    Each module (scripting, ideation, etc.) can run standalone or as
    part of a full pipeline.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._scripting_agent: ScriptingAgent | None = None

    def _get_scripting_agent(self) -> ScriptingAgent:
        if self._scripting_agent is None:
            self._scripting_agent = ScriptingAgent(self._config)
        return self._scripting_agent

    async def run_scripting(
        self,
        raw_idea: str,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> ScriptingContext:
        """Run the full 10-step scripting pipeline."""
        agent = self._get_scripting_agent()
        return await agent.run_pipeline(raw_idea, progress_callback=progress_callback)

    async def run_scripting_from_step(
        self,
        ctx: ScriptingContext,
        step: int,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> ScriptingContext:
        """Resume the scripting pipeline from a specific step."""
        agent = self._get_scripting_agent()
        return await agent.run_from_step(ctx, step, progress_callback=progress_callback)

    async def run_module(
        self,
        module: str,
        input_data: dict[str, Any],
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> ScriptingContext:
        """Run a single content gen module.

        Args:
            module: Module name (e.g. 'scripting').
            input_data: Module-specific input. For scripting, requires
                'raw_idea' or 'context' + 'from_step'.
        """
        if module == "scripting":
            ctx_data = input_data.get("context")
            from_step = input_data.get("from_step")

            if ctx_data and from_step is not None:
                ctx = ScriptingContext.model_validate(ctx_data) if isinstance(ctx_data, dict) else ctx_data
                return await self.run_scripting_from_step(ctx, from_step, progress_callback)

            return await self.run_scripting(input_data["raw_idea"], progress_callback)

        msg = f"Unknown module: {module}"
        raise ValueError(msg)
