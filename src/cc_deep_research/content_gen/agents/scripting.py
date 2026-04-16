"""Scripting agent for the 10-step short-form video script pipeline."""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from cc_deep_research.content_gen.models import (
    SCRIPTING_STEP_LABELS,
    SCRIPTING_STEPS,
    AngleDefinition,
    BeatIntent,
    BeatIntentMap,
    CoreInputs,
    CtaVariants,
    HookSet,
    QCCheck,
    QCResult,
    ScriptingContext,
    ScriptingLLMCallTrace,
    ScriptingStepTrace,
    ScriptStructure,
    ScriptVersion,
    VisualNote,
)
from cc_deep_research.content_gen.prompts import scripting as prompts
from cc_deep_research.llm import LLMRouter
from cc_deep_research.llm.base import LLMResponse, LLMTransportType

if TYPE_CHECKING:
    from cc_deep_research.config import Config

logger = logging.getLogger(__name__)

AGENT_ID = "content_gen_scripting"

# Per-step temperature defaults: creative steps get higher values,
# analytical/QC steps get lower values.
_STEP_TEMPERATURES: dict[str, float] = {
    "define_core_inputs": 0.3,
    "define_angle": 0.5,
    "choose_structure": 0.3,
    "define_beat_intents": 0.3,
    "generate_hooks": 0.7,
    "draft_script": 0.5,
    "add_retention_mechanics": 0.4,
    "tighten": 0.3,
    "add_visual_notes": 0.3,
    "run_qc": 0.2,
}

_RESET_FIELDS_BY_STEP: dict[int, tuple[str, ...]] = {
    1: (
        "core_inputs",
        "angle",
        "structure",
        "beat_intents",
        "hooks",
        "draft",
        "retention_revised",
        "tightened",
        "annotated_script",
        "visual_notes",
        "qc",
    ),
    2: (
        "angle",
        "structure",
        "beat_intents",
        "hooks",
        "draft",
        "retention_revised",
        "tightened",
        "annotated_script",
        "visual_notes",
        "qc",
    ),
    3: (
        "structure",
        "beat_intents",
        "hooks",
        "draft",
        "retention_revised",
        "tightened",
        "annotated_script",
        "visual_notes",
        "qc",
    ),
    4: (
        "beat_intents",
        "hooks",
        "draft",
        "retention_revised",
        "tightened",
        "annotated_script",
        "visual_notes",
        "qc",
    ),
    5: (
        "hooks",
        "draft",
        "retention_revised",
        "tightened",
        "annotated_script",
        "visual_notes",
        "qc",
    ),
    6: (
        "draft",
        "retention_revised",
        "tightened",
        "annotated_script",
        "visual_notes",
        "qc",
    ),
    7: ("retention_revised", "tightened", "annotated_script", "visual_notes", "qc"),
    8: ("tightened", "annotated_script", "visual_notes", "qc"),
    9: ("annotated_script", "visual_notes", "qc"),
    10: ("qc",),
}


def _transport_from_route_name(route_name: str) -> LLMTransportType:
    route_map = {
        "openrouter": LLMTransportType.OPENROUTER_API,
        "cerebras": LLMTransportType.CEREBRAS_API,
        "anthropic": LLMTransportType.ANTHROPIC_API,
        "heuristic": LLMTransportType.HEURISTIC,
    }
    transport = route_map.get(route_name)
    if transport is None:
        msg = f"Unsupported scripting LLM route: {route_name}"
        raise ValueError(msg)
    return transport


def _require(value: object, name: str, step: str) -> None:
    """Raise ValueError if *value* is None or empty string."""
    if value is None:
        msg = f"Step '{step}' requires '{name}', but it was not provided."
        raise ValueError(msg)
    if isinstance(value, str) and not value.strip():
        msg = f"Step '{step}' could not extract '{name}' from the LLM response."
        raise ValueError(msg)


class ScriptingAgent:
    """Execute the 10-step scripting pipeline for short-form video scripts."""

    def __init__(self, config: Config, *, llm_route: str | None = None) -> None:
        from cc_deep_research.llm.registry import LLMRouteRegistry

        self._config = config
        registry = LLMRouteRegistry(config.llm)
        if llm_route is not None:
            transport = _transport_from_route_name(llm_route)
            registry.set_route(AGENT_ID, registry.get_route_for_transport(transport))
        self._router = LLMRouter(registry)
        self._active_iteration = 1

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.3,
    ) -> LLMResponse:
        if not self._router.is_available(AGENT_ID):
            msg = (
                "No LLM route is available for the scripting workflow. "
                "Enable Anthropic, OpenRouter, or Cerebras with API keys before running "
                "'content-gen script'."
            )
            raise RuntimeError(msg)
        response = await self._router.execute(
            AGENT_ID,
            user_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
        )
        return response

    def _build_llm_call_trace(
        self,
        *,
        call_index: int,
        system_prompt: str,
        user_prompt: str,
        response: LLMResponse,
        temperature: float,
    ) -> ScriptingLLMCallTrace:
        return ScriptingLLMCallTrace(
            call_index=call_index,
            temperature=temperature,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            raw_response=response.content,
            provider=response.provider.value,
            model=response.model,
            transport=response.transport.value,
            latency_ms=response.latency_ms,
            prompt_tokens=int(response.usage.get("prompt_tokens", 0)),
            completion_tokens=int(response.usage.get("completion_tokens", 0)),
            finish_reason=response.finish_reason,
        )

    def _append_step_trace(
        self,
        ctx: ScriptingContext,
        *,
        step_name: str,
        llm_calls: list[ScriptingLLMCallTrace],
        parsed_output: object,
    ) -> None:
        step_index = SCRIPTING_STEPS.index(step_name)
        serialized_output = _serialize_trace_value(parsed_output)
        ctx.step_traces.append(
            ScriptingStepTrace(
                step_index=step_index,
                step_name=step_name,
                step_label=SCRIPTING_STEP_LABELS[step_name],
                iteration=self._active_iteration,
                llm_calls=llm_calls,
                parsed_output=serialized_output,
            )
        )

    # ------------------------------------------------------------------
    # Step 1: Define Core Inputs
    # ------------------------------------------------------------------

    async def define_core_inputs(self, raw_idea: str) -> ScriptingContext:
        system = prompts.STEP1_SYSTEM
        user = prompts.step1_user(raw_idea)
        response = await self._call_llm(
            system, user, temperature=_STEP_TEMPERATURES["define_core_inputs"]
        )
        text = response.content

        topic = _extract_field(text, "Topic")
        outcome = _extract_field(text, "Outcome")
        audience = _extract_field(text, "Audience")

        _require(topic, "Topic", "define_core_inputs")
        _require(outcome, "Outcome", "define_core_inputs")
        _require(audience, "Audience", "define_core_inputs")

        ctx = ScriptingContext(
            raw_idea=raw_idea,
            core_inputs=CoreInputs(topic=topic, outcome=outcome, audience=audience),
        )
        self._append_step_trace(
            ctx,
            step_name="define_core_inputs",
            llm_calls=[
                self._build_llm_call_trace(
                    call_index=1,
                    system_prompt=system,
                    user_prompt=user,
                    response=response,
                    temperature=_STEP_TEMPERATURES["define_core_inputs"],
                )
            ],
            parsed_output=ctx.core_inputs,
        )
        return ctx

    def _seed_core_inputs(
        self,
        ctx: ScriptingContext,
        *,
        raw_idea: str,
        core_inputs: CoreInputs,
        step_traces: list[ScriptingStepTrace] | None = None,
    ) -> ScriptingContext:
        ctx.raw_idea = raw_idea
        ctx.core_inputs = core_inputs
        if step_traces:
            ctx.step_traces.extend(step_traces)
        return ctx

    def _reset_outputs_from_step(self, ctx: ScriptingContext, step: int) -> None:
        for field_name in _RESET_FIELDS_BY_STEP.get(step, ()):
            setattr(ctx, field_name, None)

    # ------------------------------------------------------------------
    # Step 2: Define Angle
    # ------------------------------------------------------------------

    async def define_angle(self, ctx: ScriptingContext) -> ScriptingContext:
        if ctx.core_inputs is None:
            msg = "Step 'define_angle' requires 'core_inputs', but it was not provided."
            raise ValueError(msg)

        system = prompts.STEP2_SYSTEM
        user = prompts.step2_user(ctx.core_inputs, raw_idea=ctx.raw_idea)
        response = await self._call_llm(
            system, user, temperature=_STEP_TEMPERATURES["define_angle"]
        )
        text = response.content

        angle = _extract_field(text, "Angle")
        content_type = _extract_field(text, "Content Type")
        core_tension = _extract_field(text, "Core Tension")

        _require(angle, "Angle", "define_angle")
        _require(content_type, "Content Type", "define_angle")
        _require(core_tension, "Core Tension", "define_angle")

        ctx.angle = AngleDefinition(
            angle=angle,
            content_type=content_type,
            core_tension=core_tension,
            why_it_works=_extract_field(text, "Why this angle works"),
        )
        self._append_step_trace(
            ctx,
            step_name="define_angle",
            llm_calls=[
                self._build_llm_call_trace(
                    call_index=1,
                    system_prompt=system,
                    user_prompt=user,
                    response=response,
                    temperature=_STEP_TEMPERATURES["define_angle"],
                )
            ],
            parsed_output=ctx.angle,
        )
        return ctx

    # ------------------------------------------------------------------
    # Step 3: Choose Structure
    # ------------------------------------------------------------------

    async def choose_structure(self, ctx: ScriptingContext) -> ScriptingContext:
        if ctx.core_inputs is None:
            msg = "Step 'choose_structure' requires 'core_inputs', but it was not provided."
            raise ValueError(msg)
        if ctx.angle is None:
            msg = "Step 'choose_structure' requires 'angle', but it was not provided."
            raise ValueError(msg)

        system = prompts.STEP3_SYSTEM
        user = prompts.step3_user(ctx.core_inputs, ctx.angle, raw_idea=ctx.raw_idea)
        response = await self._call_llm(
            system, user, temperature=_STEP_TEMPERATURES["choose_structure"]
        )
        text = response.content

        chosen = _extract_field(text, "Chosen Structure")
        beats = _extract_beat_list(text)

        _require(chosen, "Chosen Structure", "choose_structure")
        if not beats:
            msg = "Step 'choose_structure' could not extract 'Beat List' from the LLM response."
            raise ValueError(msg)

        ctx.structure = ScriptStructure(
            chosen_structure=chosen,
            why_it_fits=_extract_field(text, "Why this structure fits"),
            beat_list=beats,
        )
        self._append_step_trace(
            ctx,
            step_name="choose_structure",
            llm_calls=[
                self._build_llm_call_trace(
                    call_index=1,
                    system_prompt=system,
                    user_prompt=user,
                    response=response,
                    temperature=_STEP_TEMPERATURES["choose_structure"],
                )
            ],
            parsed_output=ctx.structure,
        )
        return ctx

    # ------------------------------------------------------------------
    # Step 4: Define Beat Intents
    # ------------------------------------------------------------------

    async def define_beat_intents(self, ctx: ScriptingContext) -> ScriptingContext:
        if ctx.core_inputs is None:
            msg = "Step 'define_beat_intents' requires 'core_inputs', but it was not provided."
            raise ValueError(msg)
        if ctx.angle is None:
            msg = "Step 'define_beat_intents' requires 'angle', but it was not provided."
            raise ValueError(msg)
        if ctx.structure is None:
            msg = "Step 'define_beat_intents' requires 'structure', but it was not provided."
            raise ValueError(msg)

        system = prompts.STEP4_SYSTEM
        user = prompts.step4_user(
            ctx.core_inputs,
            ctx.angle,
            ctx.structure,
            raw_idea=ctx.raw_idea,
            research_context=ctx.research_context,
            argument_map=ctx.argument_map,
        )
        response = await self._call_llm(
            system, user, temperature=_STEP_TEMPERATURES["define_beat_intents"]
        )
        text = response.content

        beat_intents = _extract_beat_intents(text)
        if not beat_intents:
            msg = "Step 'define_beat_intents' could not extract beat intents from the LLM response."
            raise ValueError(msg)

        ctx.beat_intents = BeatIntentMap(beats=beat_intents)
        self._append_step_trace(
            ctx,
            step_name="define_beat_intents",
            llm_calls=[
                self._build_llm_call_trace(
                    call_index=1,
                    system_prompt=system,
                    user_prompt=user,
                    response=response,
                    temperature=_STEP_TEMPERATURES["define_beat_intents"],
                )
            ],
            parsed_output=ctx.beat_intents,
        )
        return ctx

    # ------------------------------------------------------------------
    # Step 5: Generate Hooks
    # ------------------------------------------------------------------

    async def generate_hooks(self, ctx: ScriptingContext) -> ScriptingContext:
        if ctx.core_inputs is None:
            msg = "Step 'generate_hooks' requires 'core_inputs', but it was not provided."
            raise ValueError(msg)
        if ctx.angle is None:
            msg = "Step 'generate_hooks' requires 'angle', but it was not provided."
            raise ValueError(msg)
        if ctx.beat_intents is None:
            msg = "Step 'generate_hooks' requires 'beat_intents', but it was not provided."
            raise ValueError(msg)

        system = prompts.STEP5_SYSTEM
        user = prompts.step5_user(
            ctx.core_inputs,
            ctx.angle,
            ctx.beat_intents,
            raw_idea=ctx.raw_idea,
            research_context=ctx.research_context,
            argument_map=ctx.argument_map,
        )
        response = await self._call_llm(
            system, user, temperature=_STEP_TEMPERATURES["generate_hooks"]
        )
        text = response.content

        hooks = _extract_numbered_list(text)
        best = _extract_field(text, "Best Hook")
        reason = _extract_field(text, "Why it is strongest")

        _require(best, "Best Hook", "generate_hooks")

        ctx.hooks = HookSet(hooks=hooks, best_hook=best, best_hook_reason=reason)
        self._append_step_trace(
            ctx,
            step_name="generate_hooks",
            llm_calls=[
                self._build_llm_call_trace(
                    call_index=1,
                    system_prompt=system,
                    user_prompt=user,
                    response=response,
                    temperature=_STEP_TEMPERATURES["generate_hooks"],
                )
            ],
            parsed_output=ctx.hooks,
        )
        return ctx

    # ------------------------------------------------------------------
    # Step 5b: Generate CTA
    # ------------------------------------------------------------------

    async def generate_cta(self, ctx: ScriptingContext) -> ScriptingContext:
        if ctx.core_inputs is None:
            msg = "Step 'generate_cta' requires 'core_inputs', but it was not provided."
            raise ValueError(msg)
        if ctx.angle is None:
            msg = "Step 'generate_cta' requires 'angle', but it was not provided."
            raise ValueError(msg)

        system = prompts.STEP5B_SYSTEM
        user = prompts.step5b_user(
            ctx.core_inputs,
            ctx.angle,
            raw_idea=ctx.raw_idea,
            research_context=ctx.research_context,
        )
        response = await self._call_llm(
            system, user, temperature=_STEP_TEMPERATURES["generate_hooks"]
        )
        text = response.content

        ctas = _extract_numbered_list(text)
        best = _extract_field(text, "Best CTA")
        reason = _extract_field(text, "Why it is strongest")

        _require(best, "Best CTA", "generate_cta")

        ctx.cta_variants = CtaVariants(ctas=ctas, best_cta=best, best_cta_reason=reason)
        self._append_step_trace(
            ctx,
            step_name="generate_cta",
            llm_calls=[
                self._build_llm_call_trace(
                    call_index=1,
                    system_prompt=system,
                    user_prompt=user,
                    response=response,
                    temperature=_STEP_TEMPERATURES["generate_hooks"],
                )
            ],
            parsed_output=ctx.cta_variants,
        )
        return ctx

    # ------------------------------------------------------------------
    # Step 6: Draft Full Script
    # ------------------------------------------------------------------

    async def draft_script(self, ctx: ScriptingContext) -> ScriptingContext:
        if ctx.core_inputs is None:
            msg = "Step 'draft_script' requires 'core_inputs', but it was not provided."
            raise ValueError(msg)
        if ctx.angle is None:
            msg = "Step 'draft_script' requires 'angle', but it was not provided."
            raise ValueError(msg)
        if ctx.structure is None:
            msg = "Step 'draft_script' requires 'structure', but it was not provided."
            raise ValueError(msg)
        if ctx.beat_intents is None:
            msg = "Step 'draft_script' requires 'beat_intents', but it was not provided."
            raise ValueError(msg)
        if ctx.hooks is None:
            msg = "Step 'draft_script' requires 'hooks', but it was not provided."
            raise ValueError(msg)

        system = prompts.STEP6_SYSTEM
        user = prompts.step6_user(
            ctx.core_inputs,
            ctx.angle,
            ctx.structure,
            ctx.beat_intents,
            ctx.hooks.best_hook,
            raw_idea=ctx.raw_idea,
            research_context=ctx.research_context,
            argument_map=ctx.argument_map,
            tone=ctx.tone,
            cta=ctx.cta,
        )
        response = await self._call_llm(
            system, user, temperature=_STEP_TEMPERATURES["draft_script"]
        )
        text = response.content
        llm_calls = [
            self._build_llm_call_trace(
                call_index=1,
                system_prompt=system,
                user_prompt=user,
                response=response,
                temperature=_STEP_TEMPERATURES["draft_script"],
            )
        ]

        if not text.strip():
            msg = "Step 'draft_script' received an empty response from the LLM."
            raise ValueError(msg)

        ctx.draft = ScriptVersion(
            content=text.strip(),
            word_count=len(text.split()),
        )

        # Re-prompt if draft significantly exceeds 120-word target
        if ctx.draft.word_count > 144:
            trim_user = (
                f"The previous draft was {ctx.draft.word_count} words. "
                f"The hard cap is 120 words.\n\n"
                f"Rewrite the script below to hit the target. "
                f"Cut filler and redundancy. Preserve the angle and all beat intents.\n\n"
                f"{ctx.draft.content}"
            )
            trim_response = await self._call_llm(system, trim_user, temperature=0.3)
            text2 = trim_response.content
            llm_calls.append(
                self._build_llm_call_trace(
                    call_index=2,
                    system_prompt=system,
                    user_prompt=trim_user,
                    response=trim_response,
                    temperature=0.3,
                )
            )
            if text2.strip():
                ctx.draft = ScriptVersion(
                    content=text2.strip(),
                    word_count=len(text2.split()),
                )

        self._append_step_trace(
            ctx,
            step_name="draft_script",
            llm_calls=llm_calls,
            parsed_output=ctx.draft,
        )
        return ctx

    # ------------------------------------------------------------------
    # Step 7: Add Retention Mechanics
    # ------------------------------------------------------------------

    async def add_retention_mechanics(self, ctx: ScriptingContext) -> ScriptingContext:
        if ctx.draft is None:
            msg = "Step 'add_retention_mechanics' requires 'draft', but it was not provided."
            raise ValueError(msg)

        system = prompts.STEP7_SYSTEM
        user = prompts.step7_user(
            ctx.draft,
            raw_idea=ctx.raw_idea,
            core_inputs=ctx.core_inputs,
            angle=ctx.angle,
            structure=ctx.structure,
            beat_intents=ctx.beat_intents,
            argument_map=ctx.argument_map,
            best_hook=ctx.hooks.best_hook if ctx.hooks else "",
            tone=ctx.tone,
            cta=ctx.cta,
            research_context=ctx.research_context,
        )
        response = await self._call_llm(
            system, user, temperature=_STEP_TEMPERATURES["add_retention_mechanics"]
        )
        text = response.content

        script_text = (
            _extract_section(
                text,
                start_marker="Revised Script:",
                end_markers=("Then add:", "Retention changes made:"),
            )
            or text
        )
        ctx.retention_revised = ScriptVersion(
            content=script_text.strip(),
            word_count=len(script_text.split()),
        )
        self._append_step_trace(
            ctx,
            step_name="add_retention_mechanics",
            llm_calls=[
                self._build_llm_call_trace(
                    call_index=1,
                    system_prompt=system,
                    user_prompt=user,
                    response=response,
                    temperature=_STEP_TEMPERATURES["add_retention_mechanics"],
                )
            ],
            parsed_output=ctx.retention_revised,
        )
        return ctx

    # ------------------------------------------------------------------
    # Step 8: Tightening Pass
    # ------------------------------------------------------------------

    async def tighten(self, ctx: ScriptingContext) -> ScriptingContext:
        source = ctx.retention_revised or ctx.draft
        if source is None:
            msg = "Step 'tighten' requires a previous script version, but none was found."
            raise ValueError(msg)

        system = prompts.STEP8_SYSTEM
        user = prompts.step8_user(
            source,
            raw_idea=ctx.raw_idea,
            core_inputs=ctx.core_inputs,
            angle=ctx.angle,
            structure=ctx.structure,
            beat_intents=ctx.beat_intents,
            argument_map=ctx.argument_map,
            best_hook=ctx.hooks.best_hook if ctx.hooks else "",
            core_tension=ctx.angle.core_tension if ctx.angle else "",
            tone=ctx.tone,
            cta=ctx.cta,
            research_context=ctx.research_context,
        )
        response = await self._call_llm(system, user, temperature=_STEP_TEMPERATURES["tighten"])
        text = response.content

        script_text = (
            _extract_section(
                text,
                start_marker="Tightened Script:",
                end_markers=("Then add:", "Cuts / improvements made:"),
            )
            or text
        )
        ctx.tightened = ScriptVersion(
            content=script_text.strip(),
            word_count=len(script_text.split()),
        )
        self._append_step_trace(
            ctx,
            step_name="tighten",
            llm_calls=[
                self._build_llm_call_trace(
                    call_index=1,
                    system_prompt=system,
                    user_prompt=user,
                    response=response,
                    temperature=_STEP_TEMPERATURES["tighten"],
                )
            ],
            parsed_output=ctx.tightened,
        )
        return ctx

    # ------------------------------------------------------------------
    # Step 9: Add Visual Notes
    # ------------------------------------------------------------------

    async def add_visual_notes(self, ctx: ScriptingContext) -> ScriptingContext:
        source = ctx.tightened or ctx.retention_revised or ctx.draft
        if source is None:
            msg = "Step 'add_visual_notes' requires a previous script version, but none was found."
            raise ValueError(msg)

        system = prompts.STEP9_SYSTEM
        user = prompts.step9_user(
            source,
            raw_idea=ctx.raw_idea,
            core_inputs=ctx.core_inputs,
            angle=ctx.angle,
            structure=ctx.structure,
            beat_intents=ctx.beat_intents,
            argument_map=ctx.argument_map,
            best_hook=ctx.hooks.best_hook if ctx.hooks else "",
            tone=ctx.tone,
            cta=ctx.cta,
            research_context=ctx.research_context,
        )
        response = await self._call_llm(
            system, user, temperature=_STEP_TEMPERATURES["add_visual_notes"]
        )
        text = response.content

        ctx.annotated_script = ScriptVersion(
            content=text.strip(),
            word_count=len(text.split()),
        )
        ctx.visual_notes = _extract_visual_notes(text)
        self._append_step_trace(
            ctx,
            step_name="add_visual_notes",
            llm_calls=[
                self._build_llm_call_trace(
                    call_index=1,
                    system_prompt=system,
                    user_prompt=user,
                    response=response,
                    temperature=_STEP_TEMPERATURES["add_visual_notes"],
                )
            ],
            parsed_output={
                "annotated_script": ctx.annotated_script,
                "visual_notes": ctx.visual_notes,
            },
        )
        return ctx

    # ------------------------------------------------------------------
    # Step 10: Final QC
    # ------------------------------------------------------------------

    async def run_qc(self, ctx: ScriptingContext) -> ScriptingContext:
        source = ctx.annotated_script or ctx.tightened or ctx.retention_revised or ctx.draft
        if source is None:
            msg = "Step 'run_qc' requires a previous script version, but none was found."
            raise ValueError(msg)

        system = prompts.STEP10_SYSTEM
        user = prompts.step10_user(
            source,
            label="Annotated Script" if ctx.annotated_script is not None else "Script",
            raw_idea=ctx.raw_idea,
            core_inputs=ctx.core_inputs,
            angle=ctx.angle,
            structure=ctx.structure,
            beat_intents=ctx.beat_intents,
            argument_map=ctx.argument_map,
            best_hook=ctx.hooks.best_hook if ctx.hooks else "",
            tone=ctx.tone,
            cta=ctx.cta,
            research_context=ctx.research_context,
        )
        response = await self._call_llm(system, user, temperature=_STEP_TEMPERATURES["run_qc"])
        text = response.content

        checks = _extract_qc_checks(text)
        weakest = _extract_weakest_parts(text)
        final = _extract_section(text, start_marker="Final Script:") or source.content

        ctx.qc = QCResult(
            checks=checks,
            weakest_parts=weakest,
            final_script=final.strip(),
        )
        self._append_step_trace(
            ctx,
            step_name="run_qc",
            llm_calls=[
                self._build_llm_call_trace(
                    call_index=1,
                    system_prompt=system,
                    user_prompt=user,
                    response=response,
                    temperature=_STEP_TEMPERATURES["run_qc"],
                )
            ],
            parsed_output=ctx.qc,
        )
        return ctx

    # ------------------------------------------------------------------
    # Pipeline runners
    # ------------------------------------------------------------------

    async def run_pipeline(
        self,
        raw_idea: str,
        progress_callback: Callable[[int, str], None] | None = None,
        *,
        iteration: int = 1,
    ) -> ScriptingContext:
        ctx = ScriptingContext(raw_idea=raw_idea)
        self._active_iteration = iteration
        try:
            for step_idx in range(len(SCRIPTING_STEPS)):
                label = SCRIPTING_STEP_LABELS[SCRIPTING_STEPS[step_idx]]
                if progress_callback:
                    progress_callback(step_idx, label)
                try:
                    ctx = await _STEP_HANDLERS[step_idx](self, ctx)
                except Exception:
                    logger.exception("Pipeline failed at step %d (%s)", step_idx + 1, label)
                    raise
        finally:
            self._active_iteration = 1
        return ctx

    async def run_from_step(
        self,
        ctx: ScriptingContext,
        step: int,
        progress_callback: Callable[[int, str], None] | None = None,
        *,
        iteration: int = 1,
    ) -> ScriptingContext:
        start_idx = step - 1
        self._reset_outputs_from_step(ctx, step)
        self._active_iteration = iteration
        try:
            for step_idx in range(start_idx, len(SCRIPTING_STEPS)):
                label = SCRIPTING_STEP_LABELS[SCRIPTING_STEPS[step_idx]]
                if progress_callback:
                    progress_callback(step_idx, label)
                try:
                    ctx = await _STEP_HANDLERS[step_idx](self, ctx)
                except Exception:
                    logger.exception("Pipeline failed at step %d (%s)", step_idx + 1, label)
                    raise
        finally:
            self._active_iteration = 1
        return ctx


# ---------------------------------------------------------------------------
# Dispatch table — replaces the if-chain
# ---------------------------------------------------------------------------

# Each handler receives (agent, ctx) except step 0 which receives (agent, raw_idea).
# We normalise this in _wrap_step0.


async def _wrap_step0(agent: ScriptingAgent, ctx: ScriptingContext) -> ScriptingContext:
    result = await agent.define_core_inputs(ctx.raw_idea)
    return agent._seed_core_inputs(
        ctx,
        raw_idea=result.raw_idea,
        core_inputs=result.core_inputs,
        step_traces=result.step_traces,
    )


_STEP_HANDLERS: list[Callable[[ScriptingAgent, ScriptingContext], Awaitable[ScriptingContext]]] = [
    _wrap_step0,
    lambda agent, ctx: agent.define_angle(ctx),
    lambda agent, ctx: agent.choose_structure(ctx),
    lambda agent, ctx: agent.define_beat_intents(ctx),
    lambda agent, ctx: agent.generate_hooks(ctx),
    lambda agent, ctx: agent.draft_script(ctx),
    lambda agent, ctx: agent.add_retention_mechanics(ctx),
    lambda agent, ctx: agent.tighten(ctx),
    lambda agent, ctx: agent.add_visual_notes(ctx),
    lambda agent, ctx: agent.run_qc(ctx),
]


# ---------------------------------------------------------------------------
# Response parsing helpers
# ---------------------------------------------------------------------------


def _extract_field(text: str, field_name: str) -> str:
    pattern = rf"{re.escape(field_name)}:\s*(.+?)(?:\n|$)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def _extract_beat_list(text: str) -> list[str]:
    section = _extract_section(text, start_marker="Beat List:") or text
    beats: list[str] = []
    for line in section.split("\n"):
        line = line.strip()
        match = re.match(r"\d+\.\s*(.+)", line)
        if match:
            beats.append(match.group(1).strip())
        elif line.startswith("- "):
            beats.append(line[2:].strip())
    return beats


def _extract_beat_intents(text: str) -> list[BeatIntent]:
    block_intents = _extract_grounded_beat_intents(text)
    if block_intents:
        return block_intents

    intents: list[BeatIntent] = []
    for line in text.split("\n"):
        match = re.match(r"[-•]?\s*\[?(.+?)\]?\s*:\s*(.+)", line.strip())
        if match:
            intents.append(
                BeatIntent(beat_name=match.group(1).strip(), intent=match.group(2).strip())
            )
    return intents


def _extract_grounded_beat_intents(text: str) -> list[BeatIntent]:
    blocks = [block.strip() for block in re.split(r"---+", text) if block.strip()]
    intents: list[BeatIntent] = []
    for block in blocks:
        beat_name = _extract_case_insensitive_field(block, "Beat Name")
        intent = _extract_case_insensitive_field(block, "Intent")
        if not beat_name or not intent:
            continue
        intents.append(
            BeatIntent(
                beat_id=_extract_case_insensitive_field(block, "Beat ID"),
                beat_name=beat_name,
                intent=intent,
                claim_ids=_extract_csv_case_insensitive_field(block, "Claim IDs"),
                proof_anchor_ids=_extract_csv_case_insensitive_field(block, "Proof Anchor IDs"),
                counterargument_ids=_extract_csv_case_insensitive_field(block, "Counterargument IDs"),
                transition_note=_extract_case_insensitive_field(block, "Transition Note"),
            )
        )
    return intents


def _extract_numbered_list(text: str) -> list[str]:
    section = _extract_section(text, start_marker=None, end_markers=("Best Hook:",)) or text
    items: list[str] = []
    for line in section.split("\n"):
        match = re.match(r"(\d+)\.\s*(.+)", line.strip())
        if match:
            items.append(match.group(2).strip())
    return items


def _extract_section(
    text: str,
    *,
    start_marker: str | None,
    end_markers: tuple[str, ...] = (),
) -> str | None:
    section = text
    if start_marker is not None:
        start_idx = text.find(start_marker)
        if start_idx == -1:
            return None
        section = text[start_idx + len(start_marker) :]

    end_positions = [section.find(marker) for marker in end_markers]
    valid_positions = [position for position in end_positions if position != -1]
    if valid_positions:
        section = section[: min(valid_positions)]

    return section.strip() or None


def _extract_visual_notes(text: str) -> list[VisualNote]:
    notes: list[VisualNote] = []
    current_beat = ""
    current_line = ""
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        bracket_match = re.match(r"\[(.+?)\]", line)
        beat_match = re.match(r"[-•]?\s*\[?(.+?)\]?\s*:\s*\"(.+?)\"", line)
        if beat_match:
            if current_beat:
                notes.append(VisualNote(beat_name=current_beat, line=current_line, note=None))
            current_beat = beat_match.group(1).strip()
            current_line = beat_match.group(2).strip()
        elif bracket_match and current_beat:
            notes.append(
                VisualNote(
                    beat_name=current_beat, line=current_line, note=f"[{bracket_match.group(1)}]"
                )
            )
            current_beat = ""
            current_line = ""
    if current_beat:
        notes.append(VisualNote(beat_name=current_beat, line=current_line, note=None))
    return notes


def _extract_qc_checks(text: str) -> list[QCCheck]:
    checks: list[QCCheck] = []
    for line in text.split("\n"):
        match = re.match(r"[-•]\s*(.+?):\s*(Pass|Fail)", line.strip(), re.IGNORECASE)
        if match:
            checks.append(
                QCCheck(item=match.group(1).strip(), passed=match.group(2).lower() == "pass")
            )
    return checks


def _extract_weakest_parts(text: str) -> list[str]:
    parts: list[str] = []
    in_section = False
    for line in text.split("\n"):
        stripped = line.strip()
        if "Weakest parts" in stripped:
            in_section = True
            continue
        if in_section:
            match = re.match(r"\d+\.\s*(.+)", stripped)
            if match:
                parts.append(match.group(1).strip())
            elif stripped and not stripped.startswith("-") and not stripped.startswith("Final"):
                break
    return parts


def _extract_case_insensitive_field(text: str, field_name: str) -> str:
    pattern = rf"(?im)^{re.escape(field_name)}:\s*(.+?)\s*$"
    match = re.search(pattern, text)
    return match.group(1).strip() if match else ""


def _extract_csv_case_insensitive_field(text: str, field_name: str) -> list[str]:
    value = _extract_case_insensitive_field(text, field_name)
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _serialize_trace_value(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")  # type: ignore[union-attr]
    if isinstance(value, list):
        return [_serialize_trace_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_trace_value(item) for key, item in value.items()}
    return value
