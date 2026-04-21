"""Scripting stage orchestrator."""

from __future__ import annotations

from typing import Any

from cc_deep_research.config import Config
from cc_deep_research.content_gen.models import ScriptingContext

from .base import BaseStageOrchestrator


class ScriptingStageOrchestrator(BaseStageOrchestrator):
    """Orchestrator for the scripting stage.

    Responsible for:
    - Running the multi-step scripting pipeline
    - Iterative refinement of scripts
    """

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def _create_agent(self, name: str) -> object:
        from cc_deep_research.content_gen.agents.scripting import ScriptingAgent

        if name == "scripting":
            return ScriptingAgent(self._config)
        raise ValueError(f"Unknown agent: {name}")

    async def run_scripting(
        self,
        idea: Any,
        *,
        llm_route: dict[str, str] | None = None,
        constraints: dict[str, Any] | None = None,
    ) -> ScriptingContext:
        """Run the scripting pipeline for an idea."""
        agent = self._get_agent("scripting")
        return await agent.run(idea, llm_route=llm_route, constraints=constraints)
