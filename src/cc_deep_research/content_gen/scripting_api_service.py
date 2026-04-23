"""Route-facing API service for scripting HTTP workflows.

This service handles HTTP-level composition (request parsing, response shaping,
error classification) while delegating domain behavior to ScriptingStore,
ScriptingAgent, and ContentGenOrchestrator.
"""

from __future__ import annotations

import json
import logging
from contextlib import suppress
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from cc_deep_research.config import Config, load_config
from cc_deep_research.content_gen.models import (
    HookSet,
    SavedScriptRun,
    ScriptingContext,
    ScriptingIterations,
    ScriptingIterationSummary,
    ScriptingRunResult,
)
from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator
from cc_deep_research.content_gen.storage import ScriptingStore

logger = logging.getLogger(__name__)


class ScriptingApiError(Exception):
    """Base class for scripting API errors."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ScriptRunNotFoundError(ScriptingApiError):
    """Raised when a script run does not exist."""

    def __init__(self, run_id: str) -> None:
        super().__init__(f"Script run not found: {run_id}", status_code=404)


class ScriptContextNotFoundError(ScriptingApiError):
    """Raised when a script context is missing and is required."""

    def __init__(self, run_id: str) -> None:
        super().__init__(
            f"Script context not found for run: {run_id}",
            status_code=400,
        )


class ScriptMissingFieldsError(ScriptingApiError):
    """Raised when a script is missing required fields for an operation."""

    def __init__(self, run_id: str, missing: str) -> None:
        super().__init__(
            f"Script is missing {missing} for run: {run_id}",
            status_code=400,
        )


class ScriptingApiService:
    """API-level service for scripting HTTP request handling.

    This class handles HTTP-specific concerns:
    - Request validation and parsing
    - Response shaping (serialization)
    - Error classification and mapping
    - HTTP workflow composition

    Domain behavior is delegated to ScriptingStore, ScriptingAgent, and
    ContentGenOrchestrator.
    """

    def __init__(
        self,
        config: Config | None = None,
        scripting_store: ScriptingStore | None = None,
        orchestrator_factory: Any | None = None,
    ) -> None:
        self._config = config or load_config()
        self._store = scripting_store or ScriptingStore()
        self._orchestrator_factory = orchestrator_factory or self._default_orchestrator_factory

    def _default_orchestrator_factory(self) -> ContentGenOrchestrator:
        return ContentGenOrchestrator(self._config)

    # ------------------------------------------------------------------
    # Run scripting
    # ------------------------------------------------------------------

    async def run_scripting(
        self,
        idea: str,
        iterative_mode: bool | None = None,
        max_iterations: int | None = None,
        llm_route: Literal["openrouter", "cerebras", "anthropic", "heuristic"] | None = None,
    ) -> ScriptingRunResult:
        """Run standalone scripting (single-pass or iterative).

        Args:
            idea: The idea/theme to script.
            iterative_mode: Whether to use iterative mode.
            max_iterations: Maximum iterations in iterative mode.
            llm_route: Optional LLM route override.

        Returns:
            ScriptingRunResult with the script and context.

        Raises:
            ScriptingApiError: If scripting fails.
        """
        orch = self._orchestrator_factory()
        iterative_enabled = (
            self._config.content_gen.enable_iterative_mode
            if iterative_mode is None
            else iterative_mode
        )

        try:
            if iterative_enabled:
                ctx, iter_state = await orch.run_scripting_iterative(
                    idea,
                    llm_route=llm_route,
                    max_iterations=max_iterations,
                )
                iterations = self._build_scripting_iterations(iter_state)
            else:
                ctx = await orch.run_scripting(idea, llm_route=llm_route)
                iterations = None
        except Exception as exc:
            logger.exception("Scripting run failed")
            raise ScriptingApiError(f"Scripting run failed: {exc}", status_code=500) from exc

        execution_mode: Literal["single_pass", "iterative"] = (
            "iterative" if iterations is not None else "single_pass"
        )
        saved = self._store.save(ctx, execution_mode=execution_mode, iterations=iterations)
        return self._build_result(ctx, run_id=saved.run_id, execution_mode=execution_mode, iterations=iterations)

    # ------------------------------------------------------------------
    # Saved scripts
    # ------------------------------------------------------------------

    def list_scripts(self, limit: int = 50) -> list[dict[str, Any]]:
        """List saved script runs.

        Args:
            limit: Maximum number of runs to return.

        Returns:
            List of serialized SavedScriptRun dicts.
        """
        runs = self._store.list_runs(limit=limit)
        return [self._serialize_saved_run(r) for r in runs]

    def get_script(self, run_id: str) -> ScriptingRunResult:
        """Get a specific script run with full context.

        Args:
            run_id: ID of the script run.

        Returns:
            ScriptingRunResult with the script.

        Raises:
            ScriptRunNotFoundError: If run doesn't exist.
        """
        run = self._store.get(run_id)
        if run is None:
            raise ScriptRunNotFoundError(run_id)

        # Try to load full result from result_path first
        result_text = ""
        with suppress(Exception):
            if run.result_path:
                result_text = Path(run.result_path).read_text()

        if result_text:
            with suppress(json.JSONDecodeError):
                result_data = json.loads(result_text)
                return ScriptingRunResult(**result_data)

        # Fall back to building from stored parts
        script_text = ""
        with suppress(Exception):
            script_text = Path(run.script_path).read_text()

        context: ScriptingContext | None = None
        with suppress(Exception):
            context_text = Path(run.context_path).read_text()
            if context_text:
                context = ScriptingContext.model_validate_json(context_text)

        if context is None:
            context = ScriptingContext(raw_idea=run.raw_idea)

        response = self._build_result(
            context,
            run_id=run.run_id,
            execution_mode=run.execution_mode,
            iterations=run.iterations,
        )
        if script_text:
            response.script = script_text
            response.word_count = len(script_text.split())

        return response

    # ------------------------------------------------------------------
    # Variant generation
    # ------------------------------------------------------------------

    async def generate_variants(
        self,
        run_id: str,
        tone: str | None = None,
        cta_goal: str | None = None,
    ) -> dict[str, Any]:
        """Generate new hook and CTA variants for an existing script run.

        Args:
            run_id: ID of the script run to generate variants for.
            tone: Optional tone override.
            cta_goal: Optional CTA goal override.

        Returns:
            Dict with hooks and cta_variants.

        Raises:
            ScriptRunNotFoundError: If run doesn't exist.
            ScriptContextNotFoundError: If script context is missing.
            ScriptMissingFieldsError: If core_inputs or angle are missing.
        """
        run = self._store.get(run_id)
        if run is None:
            raise ScriptRunNotFoundError(run_id)

        # Load context
        context: ScriptingContext | None = None
        try:
            if run.context_path:
                context_text = Path(run.context_path).read_text()
                if context_text:
                    context = ScriptingContext.model_validate_json(context_text)
        except (FileNotFoundError, json.JSONDecodeError, ValidationError):
            pass

        if context is None:
            raise ScriptContextNotFoundError(run_id)

        if context.core_inputs is None or context.angle is None:
            raise ScriptMissingFieldsError(run_id, "core_inputs or angle")

        # Override tone/CTA if provided
        if tone is not None:
            context.tone = tone
        if cta_goal is not None:
            context.cta = cta_goal

        # Generate hooks and CTA using ScriptingAgent
        from cc_deep_research.content_gen.agents.scripting import ScriptingAgent
        from cc_deep_research.llm import LLMRouter

        llm = LLMRouter(self._config.content_gen.llm)
        agent = ScriptingAgent(llm)

        context = await agent.generate_hooks(context)
        context = await agent.generate_cta(context)

        # Save updated context
        self._store._save_context(run_id, context)

        return {
            "hooks": json.loads(context.hooks.model_dump_json()) if context.hooks else {},
            "cta_variants": json.loads(context.cta_variants.model_dump_json()) if context.cta_variants else {},
        }

    # ------------------------------------------------------------------
    # Script update
    # ------------------------------------------------------------------

    def update_script(
        self,
        run_id: str,
        hook: str | None = None,
        cta: str | None = None,
        script: str | None = None,
    ) -> dict[str, Any]:
        """Update a script run with new hook, CTA, or full script content.

        Args:
            run_id: ID of the script run to update.
            hook: New hook text.
            cta: New CTA text.
            script: New full script text.

        Returns:
            Dict with success status and run_id.

        Raises:
            ScriptRunNotFoundError: If run doesn't exist.
            ScriptContextNotFoundError: If script context is missing.
        """
        if hook is None and cta is None and script is None:
            raise ScriptingApiError(
                "At least one field (hook, cta, or script) must be provided",
                status_code=400,
            )

        run = self._store.get(run_id)
        if run is None:
            raise ScriptRunNotFoundError(run_id)

        # Load context
        context: ScriptingContext | None = None
        try:
            if run.context_path:
                context_text = Path(run.context_path).read_text()
                if context_text:
                    context = ScriptingContext.model_validate_json(context_text)
        except (FileNotFoundError, json.JSONDecodeError, ValidationError):
            pass

        if context is None:
            raise ScriptContextNotFoundError(run_id)

        # Update fields
        if hook is not None:
            if context.hooks is None:
                context.hooks = HookSet(hooks=[], best_hook=hook, best_hook_reason="")
            else:
                context.hooks.best_hook = hook

        if cta is not None:
            context.cta = cta

        if script is not None:
            script_path = Path(run.script_path)
            script_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.write_text(script)

        # Save updated context
        self._store._save_context(run_id, context)

        return {"success": True, "run_id": run_id}

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    @staticmethod
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

    def _build_result(
        self,
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

    @staticmethod
    def _serialize_saved_run(run: SavedScriptRun) -> dict[str, Any]:
        payload = run.model_dump(mode="json")
        if payload.get("iterations") is None:
            payload.pop("iterations", None)
        return payload

    @staticmethod
    def serialize_result(result: ScriptingRunResult) -> dict[str, Any]:
        """Serialize a ScriptingRunResult to JSON-compatible dict."""
        payload = result.model_dump(mode="json")
        if payload.get("iterations") is None:
            payload.pop("iterations", None)
        return payload
