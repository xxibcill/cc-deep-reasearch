"""Quality evaluator agent for iterative content generation."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from cc_deep_research.content_gen.agents._llm_utils import call_agent_llm_text
from cc_deep_research.content_gen.models import (
    AngleOutput,
    ArgumentMap,
    BeatRevisionScope,
    PackagingOutput,
    QualityEvaluation,
    ResearchPack,
    RevisionMode,
    RewriteActionType,
    ScriptingContext,
    TargetedRevisionPlan,
    TargetedRewriteAction,
    VisualPlanOutput,
)
from cc_deep_research.content_gen.prompts import quality_evaluator as prompts
from cc_deep_research.llm import LLMRouter

if TYPE_CHECKING:
    from cc_deep_research.config import Config

logger = logging.getLogger(__name__)

AGENT_ID = "content_gen_quality_evaluator"


class QualityEvaluatorAgent:
    """Evaluate content quality after each iteration and decide whether to continue."""

    def __init__(self, config: Config) -> None:
        from cc_deep_research.llm.registry import LLMRouteRegistry

        self._config = config
        registry = LLMRouteRegistry(config.llm)
        self._router = LLMRouter(registry)

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
    ) -> str:
        return await call_agent_llm_text(
            router=self._router,
            agent_id=AGENT_ID,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            workflow_name="quality evaluation workflow",
            cli_command="content-gen script",
            logger=logger,
        )

    async def evaluate(
        self,
        *,
        scripting: ScriptingContext,
        visual_plan: VisualPlanOutput | None = None,
        packaging: PackagingOutput | None = None,
        research_pack: ResearchPack | None = None,
        argument_map: ArgumentMap | None = None,
        angle: AngleOutput | None = None,
        iteration_number: int = 1,
        quality_threshold: float = 0.75,
        previous_feedback: str = "",
    ) -> QualityEvaluation:
        script = _extract_final_script(scripting)
        system = prompts.EVALUATOR_SYSTEM
        user = prompts.evaluator_user(
            script=script,
            visual_summary=_summarize_visual(visual_plan),
            packaging_summary=_summarize_packaging(packaging),
            research_summary=_summarize_research(research_pack),
            argument_map_summary=_summarize_argument_map(argument_map),
            angle_summary=_summarize_angle(angle),
            iteration_number=iteration_number,
            quality_threshold=quality_threshold,
            previous_feedback=previous_feedback,
        )
        text = await self._call_llm(system, user, temperature=0.2)
        return _parse_quality_evaluation(text, iteration_number)

    async def evaluate_scripting(
        self,
        *,
        scripting: ScriptingContext,
        iteration_number: int = 1,
        quality_threshold: float = 0.75,
        previous_feedback: str = "",
    ) -> QualityEvaluation:
        """Evaluate quality for standalone scripting runs (no visual/packaging context)."""
        return await self.evaluate(
            scripting=scripting,
            iteration_number=iteration_number,
            quality_threshold=quality_threshold,
            previous_feedback=previous_feedback,
        )


# ---------------------------------------------------------------------------
# Summarization helpers
# ---------------------------------------------------------------------------


def _extract_final_script(scripting: ScriptingContext) -> str:
    if scripting.qc and scripting.qc.final_script:
        return scripting.qc.final_script
    if scripting.tightened:
        return scripting.tightened.content
    if scripting.draft:
        return scripting.draft.content
    return ""


def _summarize_visual(visual_plan: VisualPlanOutput | None) -> str:
    if not visual_plan or not visual_plan.visual_plan:
        return ""
    return "\n".join(f"- {bv.beat}: {bv.visual}" for bv in visual_plan.visual_plan[:5])


def _summarize_packaging(packaging: PackagingOutput | None) -> str:
    if not packaging or not packaging.platform_packages:
        return ""
    return "\n".join(f"- {p.platform}: {p.primary_hook}" for p in packaging.platform_packages)


def _summarize_research(research_pack: ResearchPack | None) -> str:
    if not research_pack:
        return ""
    parts = []
    if research_pack.claims:
        supported_claims = [claim.claim for claim in research_pack.claims[:4] if claim.claim]
        if supported_claims:
            parts.append("Supported claims:\n- " + "\n- ".join(supported_claims))
    else:
        if research_pack.key_facts:
            parts.append("Key facts:\n- " + "\n- ".join(research_pack.key_facts[:3]))
        if research_pack.proof_points:
            parts.append("Proof points:\n- " + "\n- ".join(research_pack.proof_points[:3]))
    if research_pack.claims_requiring_verification:
        parts.append(
            "Needs verification:\n- "
            + "\n- ".join(research_pack.claims_requiring_verification[:3])
        )
    if research_pack.unsafe_or_uncertain_claims:
        parts.append(
            "Unsafe or uncertain claims:\n- "
            + "\n- ".join(research_pack.unsafe_or_uncertain_claims[:3])
        )
    return "\n\n".join(parts)


def _summarize_argument_map(argument_map: ArgumentMap | None) -> str:
    if not argument_map:
        return ""
    parts = []
    if argument_map.thesis:
        parts.append(f"Thesis: {argument_map.thesis}")
    if argument_map.core_mechanism:
        parts.append(f"Core mechanism: {argument_map.core_mechanism}")
    if argument_map.safe_claims:
        safe_claims = [claim.claim for claim in argument_map.safe_claims[:4] if claim.claim]
        if safe_claims:
            parts.append("Safe claims:\n- " + "\n- ".join(safe_claims))
    if argument_map.unsafe_claims:
        unsafe_claims = [claim.claim for claim in argument_map.unsafe_claims[:3] if claim.claim]
        if unsafe_claims:
            parts.append("Claims to avoid or qualify:\n- " + "\n- ".join(unsafe_claims))
    if argument_map.proof_anchors:
        proof_anchors = [
            anchor.summary for anchor in argument_map.proof_anchors[:4] if anchor.summary
        ]
        if proof_anchors:
            parts.append("Proof anchors:\n- " + "\n- ".join(proof_anchors))
    return "\n\n".join(part for part in parts if part)


def _summarize_angle(angle: AngleOutput | None) -> str:
    if not angle or not angle.angle_options:
        return ""
    selected = next(
        (a for a in angle.angle_options if a.angle_id == angle.selected_angle_id),
        angle.angle_options[0],
    )
    return f"Angle: {selected.core_promise}\nAudience: {selected.target_audience}"


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _extract_score(text: str, field_name: str) -> float:
    pattern = rf"{re.escape(field_name)}:\s*([-+]?\d*\.?\d+)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        try:
            return min(1.0, max(0.0, float(match.group(1))))
        except ValueError:
            pass
    return 0.0


def _extract_bool(text: str, field_name: str) -> bool:
    pattern = rf"{re.escape(field_name)}:\s*(true|false)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).lower() == "true"
    return False


def _extract_field(text: str, field_name: str) -> str:
    pattern = rf"{re.escape(field_name)}:\s*(.+?)(?:\n|$)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def _extract_list(text: str, header: str) -> list[str]:
    items: list[str] = []
    in_section = False
    for line in text.split("\n"):
        stripped = line.strip()
        if header.lower().replace("_", " ") in stripped.lower().replace("_", " "):
            in_section = True
            continue
        if in_section:
            if stripped.startswith("- ") or stripped.startswith("* "):
                items.append(stripped[2:].strip())
            elif (
                stripped
                and not stripped.startswith("-")
                and not stripped.startswith("*")
                and re.match(r"[a-z_]+:", stripped)
            ):
                break
    return items


def _parse_quality_evaluation(text: str, iteration_number: int) -> QualityEvaluation:
    unsupported_claims = _extract_list(text, "unsupported_claims")
    parsed_passes_threshold = _extract_bool(text, "passes_threshold")

    # Parse revision mode
    revision_mode_str = _extract_field(text, "revision_mode").strip().lower()
    if revision_mode_str == "targeted":
        revision_mode = RevisionMode.TARGETED
    elif revision_mode_str == "full":
        revision_mode = RevisionMode.FULL
    else:
        revision_mode = RevisionMode.NONE

    # Parse targeted revision plan (only if revision_mode is targeted or full)
    targeted_plan = None
    if revision_mode != RevisionMode.NONE:
        targeted_plan = _parse_targeted_revision_plan(text)

    return QualityEvaluation(
        overall_quality_score=_extract_score(text, "overall_quality_score"),
        passes_threshold=parsed_passes_threshold and not unsupported_claims,
        evidence_coverage=_extract_score(text, "evidence_coverage"),
        claim_safety=_extract_score(text, "claim_safety"),
        originality=_extract_score(text, "originality"),
        precision=_extract_score(text, "precision"),
        expertise_density=_extract_score(text, "expertise_density"),
        critical_issues=_extract_list(text, "critical_issues"),
        unsupported_claims=unsupported_claims,
        evidence_actions_required=_extract_list(text, "evidence_actions_required"),
        improvement_suggestions=_extract_list(text, "improvement_suggestions"),
        research_gaps_identified=_extract_list(text, "research_gaps_identified"),
        rationale=_extract_field(text, "rationale"),
        iteration_number=iteration_number,
        targeted_revision_plan=targeted_plan,
        revision_mode=revision_mode,
    )


def _parse_targeted_revision_plan(text: str) -> TargetedRevisionPlan | None:
    """Parse the targeted revision plan section from evaluator output."""
    plan_text = _extract_section(text, start_marker="targeted_revision_plan:")
    if not plan_text:
        return None

    revision_summary = _extract_field(plan_text, "revision_summary")

    # Parse full_restart_recommended
    restart_str = _extract_field(plan_text, "full_restart_recommended")
    full_restart_recommended = restart_str.strip().lower() == "true" if restart_str else False

    # Parse is_patch
    is_patch_str = _extract_field(plan_text, "is_patch")
    is_patch = is_patch_str.strip().lower() != "false" if is_patch_str else True

    # Parse stable_beats
    stable_beats_text = _extract_named_subsection(plan_text, "stable_beats")
    stable_beats = _parse_beat_revision_list(stable_beats_text, is_stable=True) if stable_beats_text else []

    # Parse weak_beats
    weak_beats_text = _extract_named_subsection(plan_text, "weak_beats")
    weak_beats = _parse_beat_revision_list(weak_beats_text, is_stable=False) if weak_beats_text else []

    # Parse actions
    actions_text = _extract_named_subsection(plan_text, "actions")
    actions = _parse_rewrite_actions(actions_text) if actions_text else []

    # Parse retrieval_gaps
    retrieval_gaps = _extract_list(plan_text, "retrieval_gaps")

    return TargetedRevisionPlan(
        revision_summary=revision_summary,
        full_restart_recommended=full_restart_recommended,
        is_patch=is_patch,
        stable_beats=stable_beats,
        weak_beats=weak_beats,
        actions=actions,
        retrieval_gaps=retrieval_gaps,
    )


def _parse_beat_revision_list(section_text: str, *, is_stable: bool) -> list[BeatRevisionScope]:
    """Parse a list of beat revision scope entries."""
    if not section_text:
        return []

    beats: list[BeatRevisionScope] = []
    for block in _extract_blocks(section_text):
        beat_id = _extract_block_field(block, "beat_id")
        beat_name = _extract_block_field(block, "beat_name")
        if not beat_name and not beat_id:
            continue

        weak_claim_ids = _extract_csv_field(block, "weak_claim_ids")
        missing_proof_ids = _extract_csv_field(block, "missing_proof_ids")
        weakness_reason = _extract_block_field(block, "weakness_reason")

        beats.append(
            BeatRevisionScope(
                beat_id=beat_id or beat_name,
                beat_name=beat_name,
                weak_claim_ids=weak_claim_ids if weak_claim_ids else [],
                missing_proof_ids=missing_proof_ids if missing_proof_ids else [],
                weakness_reason=weakness_reason,
                is_stable=is_stable,
            )
        )
    return beats


def _parse_rewrite_actions(section_text: str) -> list[TargetedRewriteAction]:
    """Parse a list of targeted rewrite actions."""
    if not section_text:
        return []

    actions: list[TargetedRewriteAction] = []
    for block in _extract_blocks(section_text):
        action_type_str = _extract_block_field(block, "action_type").strip().lower()
        if not action_type_str:
            continue

        try:
            action_type = RewriteActionType(action_type_str)
        except ValueError:
            continue

        instruction = _extract_block_field(block, "instruction")
        if not instruction:
            # Build instruction from type and context
            beat_name = _extract_block_field(block, "beat_name") or ""
            weak_claims = ", ".join(_extract_csv_field(block, "weak_claim_ids"))
            if action_type == RewriteActionType.REWRITE_BEAT:
                instruction = f"Rewrite beat '{beat_name}' — weak claims: {weak_claims}"
            elif action_type == RewriteActionType.REFRESH_EVIDENCE:
                instruction = f"Refresh evidence for beat '{beat_name}'"
            elif action_type == RewriteActionType.QUALIFY_CLAIM:
                target = _extract_block_field(block, "target_claim_text")
                instruction = f"Qualify claim: {target}"
            elif action_type == RewriteActionType.REMOVE_CLAIM:
                target = _extract_block_field(block, "target_claim_text")
                instruction = f"Remove claim: {target}"
            elif action_type == RewriteActionType.ADD_COUNTERARGUMENT:
                instruction = f"Add counterargument coverage for beat '{beat_name}'"

        actions.append(
            TargetedRewriteAction(
                action_type=action_type,
                beat_id=_extract_block_field(block, "beat_id"),
                beat_name=_extract_block_field(block, "beat_name"),
                weak_claim_ids=_extract_csv_field(block, "weak_claim_ids"),
                missing_proof_ids=_extract_csv_field(block, "missing_proof_ids"),
                target_claim_text=_extract_block_field(block, "target_claim_text"),
                target_claim_id=_extract_block_field(block, "target_claim_id"),
                instruction=instruction,
                evidence_gaps=_extract_csv_field(block, "evidence_gaps"),
                priority=int(_extract_block_field(block, "priority") or "5"),
            )
        )
    return actions


def _extract_named_subsection(text: str, subsection: str) -> str:
    """Extract a named subsection block from section text."""
    return _extract_section(text, start_marker=f"{subsection}:") or ""


def _extract_blocks(section_text: str) -> list[str]:
    if not section_text.strip():
        return []
    return [block.strip() for block in re.split(r"---+", section_text) if block.strip()]


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


def _extract_block_field(text: str, field_name: str) -> str:
    return _extract_field(text, field_name)


def _extract_csv_field(text: str, field_name: str) -> list[str]:
    value = _extract_block_field(text, field_name)
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]
