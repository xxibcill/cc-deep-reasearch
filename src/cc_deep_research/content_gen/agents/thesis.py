"""Thesis generator agent - P3-T2 unified angle + argument design."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from cc_deep_research.content_gen.agents._llm_utils import call_agent_llm_text
from cc_deep_research.content_gen.models import (
    ArgumentBeatClaim,
    ArgumentClaim,
    ArgumentCounterargument,
    ArgumentProofAnchor,
    BacklogItem,
    ResearchPack,
    StrategyMemory,
    ThesisArtifact,
)
from cc_deep_research.content_gen.prompts import thesis as prompts
from cc_deep_research.llm import LLMRouter

if TYPE_CHECKING:
    from cc_deep_research.config import Config

logger = logging.getLogger(__name__)

AGENT_ID = "content_gen_thesis"


class ThesisAgent:
    """Generate a unified thesis artifact combining angle selection with argument design.

    P3-T2: This agent replaces the previous two-stage flow of:
    1. AngleAgent.generate() -> AngleOutput (multiple options + selection)
    2. ArgumentMapAgent.build() -> ArgumentMap (thesis + claims + beats)

    Now produces a single ThesisArtifact in one pass that includes:
    - Selected angle fields (target_audience, viewer_problem, core_promise, etc.)
    - Thesis structure (thesis, audience_belief_to_challenge, core_mechanism)
    - Support structure (proof_anchors, claims, counterarguments, beats)
    """

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
        temperature: float = 0.4,
    ) -> str:
        return await call_agent_llm_text(
            router=self._router,
            agent_id=AGENT_ID,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            workflow_name="thesis generation workflow",
            cli_command="content-gen pipeline",
            logger=logger,
        )

    async def build(
        self,
        item: BacklogItem,
        strategy: StrategyMemory,
        *,
        research_pack: ResearchPack | None = None,
    ) -> ThesisArtifact:
        """Build a unified thesis artifact.

        Args:
            item: The backlog item to develop into a thesis
            strategy: Strategy memory for brand/audience guidance
            research_pack: Optional research pack for evidence context

        Returns:
            ThesisArtifact containing angle selection and argument structure
        """
        system = prompts.THESIS_SYSTEM
        user = prompts.thesis_user(item, strategy, research_pack)
        text = await self._call_llm(system, user, temperature=0.4)
        return _parse_thesis_artifact(text, item.idea_id)


def _extract_field(text: str, field_name: str) -> str:
    """Extract a scalar field value from the output."""
    pattern = rf"{re.escape(field_name)}:\s*(.+?)(?:\n|$)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def _extract_list_field(text: str, field_name: str) -> list[str]:
    """Extract a '-' list field from a block."""
    lines = text.split("\n")
    field_line_idx = -1
    for i, line in enumerate(lines):
        if re.match(rf"^{re.escape(field_name)}:\s*$", line.strip(), re.IGNORECASE):
            field_line_idx = i
            break

    if field_line_idx == -1:
        return []

    items: list[str] = []
    for line in lines[field_line_idx + 1 :]:
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            items.append(stripped[2:].strip())
        elif stripped == "":
            continue
        else:
            break

    return items


def _extract_section(text: str, section_name: str) -> str | None:
    """Extract a named section block from the output."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if re.match(rf"^{re.escape(section_name)}:\s*$", line.strip(), re.IGNORECASE):
            # Collect lines until we hit another section header or end
            section_lines = []
            for j in range(i + 1, len(lines)):
                next_line = lines[j].strip()
                # Stop if we hit another top-level section
                if next_line and not next_line.startswith("-"):
                    # Check if it's a new section header
                    if re.match(r"^[A-Z][A-Z_ ]+[:]?\s*$", next_line):
                        break
                    # Check if it's a field name
                    if re.match(r"^[a-z_]+:\s*", next_line):
                        break
                section_lines.append(next_line)
            return "\n".join(section_lines).strip()
    return None


def _parse_proof_anchors(section_text: str | None) -> list[ArgumentProofAnchor]:
    """Parse proof_anchor blocks from section text."""
    if not section_text:
        return []
    anchors = []
    blocks = re.split(r"---+", section_text)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        proof_id = _extract_field(block, "proof_id")
        if not proof_id:
            proof_id = f"proof_{len(anchors) + 1}"
        anchors.append(
            ArgumentProofAnchor(
                proof_id=proof_id,
                summary=_extract_field(block, "summary"),
                source_ids=[
                    s.strip() for s in _extract_field(block, "source_ids").split(",") if s.strip()
                ],
                usage_note=_extract_field(block, "usage_note"),
            )
        )
    return anchors


def _parse_counterarguments(section_text: str | None) -> list[ArgumentCounterargument]:
    """Parse counterargument blocks from section text."""
    if not section_text:
        return []
    counterargs = []
    blocks = re.split(r"---+", section_text)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        counterargument_id = _extract_field(block, "counterargument_id")
        if not counterargument_id:
            counterargument_id = f"counter_{len(counterargs) + 1}"
        counterargs.append(
            ArgumentCounterargument(
                counterargument_id=counterargument_id,
                counterargument=_extract_field(block, "counterargument"),
                response=_extract_field(block, "response"),
                response_proof_ids=[
                    s.strip()
                    for s in _extract_field(block, "response_proof_ids").split(",")
                    if s.strip()
                ],
            )
        )
    return counterargs


def _parse_claims(section_text: str | None) -> list[ArgumentClaim]:
    """Parse claim blocks from section text."""
    if not section_text:
        return []
    claims = []
    blocks = re.split(r"---+", section_text)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        claim_id = _extract_field(block, "claim_id")
        if not claim_id:
            claim_id = f"claim_{len(claims) + 1}"
        claims.append(
            ArgumentClaim(
                claim_id=claim_id,
                claim=_extract_field(block, "claim"),
                supporting_proof_ids=[
                    s.strip()
                    for s in _extract_field(block, "supporting_proof_ids").split(",")
                    if s.strip()
                ],
                note=_extract_field(block, "note"),
            )
        )
    return claims


def _parse_beats(section_text: str | None) -> list[ArgumentBeatClaim]:
    """Parse beat_claim_plan blocks from section text."""
    if not section_text:
        return []
    beats = []
    blocks = re.split(r"---+", section_text)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        beat_id = _extract_field(block, "beat_id")
        if not beat_id:
            beat_id = f"beat_{len(beats) + 1}"
        beats.append(
            ArgumentBeatClaim(
                beat_id=beat_id,
                beat_name=_extract_field(block, "beat_name"),
                goal=_extract_field(block, "goal"),
                claim_ids=[
                    s.strip() for s in _extract_field(block, "claim_ids").split(",") if s.strip()
                ],
                proof_anchor_ids=[
                    s.strip()
                    for s in _extract_field(block, "proof_anchor_ids").split(",")
                    if s.strip()
                ],
                counterargument_ids=[
                    s.strip()
                    for s in _extract_field(block, "counterargument_ids").split(",")
                    if s.strip()
                ],
                transition_note=_extract_field(block, "transition_note"),
            )
        )
    return beats


def _parse_thesis_artifact(text: str, idea_id: str) -> ThesisArtifact:
    """Parse the unified thesis artifact from LLM output.

    The output format combines angle fields and thesis/argument fields in one pass.
    """
    # Extract angle selection fields
    angle_id = _extract_field(text, "angle_id")
    if not angle_id:
        angle_id = "angle_1"

    # Extract thesis core fields
    thesis = _extract_field(text, "thesis")
    audience_belief_to_challenge = _extract_field(text, "audience_belief_to_challenge")
    core_mechanism = _extract_field(text, "core_mechanism")

    if not thesis:
        raise ValueError(
            "Thesis parsing failed: missing required field 'thesis'. "
            "Ensure the output includes the thesis statement."
        )

    # Extract structured sections
    proof_section = _extract_section(text, "proof_anchors")
    counter_section = _extract_section(text, "counterarguments")
    safe_claims_section = _extract_section(text, "safe_claims")
    unsafe_claims_section = _extract_section(text, "unsafe_claims")
    beats_section = _extract_section(text, "beat_claim_plan")

    proof_anchors = _parse_proof_anchors(proof_section)
    counterarguments = _parse_counterarguments(counter_section)
    safe_claims = _parse_claims(safe_claims_section)
    unsafe_claims = _parse_claims(unsafe_claims_section)
    beat_claim_plan = _parse_beats(beats_section)

    # Extract list fields
    genericity_risks = _extract_list_field(text, "genericity_risks")
    genericity_flags = _extract_list_field(text, "genericity_flags")

    return ThesisArtifact(
        idea_id=idea_id,
        angle_id=angle_id,
        target_audience=_extract_field(text, "target_audience"),
        viewer_problem=_extract_field(text, "viewer_problem"),
        core_promise=_extract_field(text, "core_promise"),
        primary_takeaway=_extract_field(text, "primary_takeaway"),
        lens=_extract_field(text, "lens"),
        format=_extract_field(text, "format"),
        tone=_extract_field(text, "tone"),
        cta=_extract_field(text, "cta"),
        why_this_version_should_exist=_extract_field(text, "why_this_version_should_exist"),
        differentiation_summary=_extract_field(text, "differentiation_summary"),
        genericity_risks=genericity_risks,
        market_framing_challenged=_extract_field(text, "market_framing_challenged"),
        thesis=thesis,
        audience_belief_to_challenge=audience_belief_to_challenge,
        core_mechanism=core_mechanism,
        proof_anchors=proof_anchors,
        counterarguments=counterarguments,
        safe_claims=safe_claims,
        unsafe_claims=unsafe_claims,
        beat_claim_plan=beat_claim_plan,
        what_this_contributes=_extract_field(text, "what_this_contributes"),
        genericity_flags=genericity_flags,
        differentiation_stategy=_extract_field(text, "differentiation_stategy"),
        selection_reasoning=_extract_field(text, "selection_reasoning"),
    )
