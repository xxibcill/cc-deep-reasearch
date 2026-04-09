"""Argument map builder agent."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from pydantic import ValidationError

from cc_deep_research.content_gen.models import (
    AngleOption,
    ArgumentBeatClaim,
    ArgumentClaim,
    ArgumentCounterargument,
    ArgumentMap,
    ArgumentProofAnchor,
    BacklogItem,
    ResearchPack,
)
from cc_deep_research.content_gen.prompts import argument_map as prompts
from cc_deep_research.llm import LLMRouter

if TYPE_CHECKING:
    from cc_deep_research.config import Config

logger = logging.getLogger(__name__)

AGENT_ID = "content_gen_argument_map"

_SECTION_HEADERS = (
    "proof_anchors",
    "counterarguments",
    "safe_claims",
    "unsafe_claims",
    "beat_claim_plan",
)


class ArgumentMapAgent:
    """Build a validated argument map from idea, angle, and research evidence."""

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
        temperature: float = 0.3,
    ) -> str:
        response = await self._router.execute(
            AGENT_ID,
            user_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
        )
        return response.content

    async def build(
        self,
        item: BacklogItem,
        angle: AngleOption,
        research_pack: ResearchPack,
    ) -> ArgumentMap:
        system = prompts.ARGUMENT_MAP_SYSTEM
        user = prompts.argument_map_user(item, angle, research_pack)
        text = await self._call_llm(system, user, temperature=0.3)
        return _parse_argument_map(text, item.idea_id, angle.angle_id)


def _parse_argument_map(text: str, idea_id: str, angle_id: str) -> ArgumentMap:
    thesis = _extract_field(text, "thesis")
    audience_belief_to_challenge = _extract_field(text, "audience_belief_to_challenge")
    core_mechanism = _extract_field(text, "core_mechanism")

    proof_anchors = _parse_proof_anchors(_extract_named_section(text, "proof_anchors"))
    counterarguments = _parse_counterarguments(_extract_named_section(text, "counterarguments"))
    safe_claims = _parse_claims(_extract_named_section(text, "safe_claims"))
    unsafe_claims = _parse_claims(_extract_named_section(text, "unsafe_claims"))
    beat_claim_plan = _parse_beats(_extract_named_section(text, "beat_claim_plan"))

    if not thesis:
        raise ValueError("Argument map parsing failed: missing required field 'thesis'.")
    if not core_mechanism:
        raise ValueError("Argument map parsing failed: missing required field 'core_mechanism'.")
    if not proof_anchors:
        raise ValueError("Argument map parsing failed: missing at least one proof anchor.")

    try:
        return ArgumentMap(
            idea_id=idea_id,
            angle_id=angle_id,
            thesis=thesis,
            audience_belief_to_challenge=audience_belief_to_challenge,
            core_mechanism=core_mechanism,
            proof_anchors=proof_anchors,
            counterarguments=counterarguments,
            safe_claims=safe_claims,
            unsafe_claims=unsafe_claims,
            beat_claim_plan=beat_claim_plan,
        )
    except ValidationError as exc:
        msg = f"Argument map parsing failed: {exc.errors()[0]['msg']}"
        raise ValueError(msg) from exc


def _parse_proof_anchors(section_text: str) -> list[ArgumentProofAnchor]:
    anchors: list[ArgumentProofAnchor] = []
    for block in _extract_blocks(section_text):
        proof_id = _extract_block_field(block, "proof_id")
        summary = _extract_block_field(block, "summary")
        if not proof_id or not summary:
            continue
        anchors.append(
            ArgumentProofAnchor(
                proof_id=proof_id,
                summary=summary,
                source_ids=_extract_csv_field(block, "source_ids"),
                usage_note=_extract_block_field(block, "usage_note"),
            )
        )
    return anchors


def _parse_counterarguments(section_text: str) -> list[ArgumentCounterargument]:
    counterarguments: list[ArgumentCounterargument] = []
    for block in _extract_blocks(section_text):
        counterargument_id = _extract_block_field(block, "counterargument_id")
        counterargument = _extract_block_field(block, "counterargument")
        if not counterargument_id or not counterargument:
            continue
        counterarguments.append(
            ArgumentCounterargument(
                counterargument_id=counterargument_id,
                counterargument=counterargument,
                response=_extract_block_field(block, "response"),
                response_proof_ids=_extract_csv_field(block, "response_proof_ids"),
            )
        )
    return counterarguments


def _parse_claims(section_text: str) -> list[ArgumentClaim]:
    claims: list[ArgumentClaim] = []
    for block in _extract_blocks(section_text):
        claim_id = _extract_block_field(block, "claim_id")
        claim = _extract_block_field(block, "claim")
        if not claim_id or not claim:
            continue
        claims.append(
            ArgumentClaim(
                claim_id=claim_id,
                claim=claim,
                supporting_proof_ids=_extract_csv_field(block, "supporting_proof_ids"),
                note=_extract_block_field(block, "note"),
            )
        )
    return claims


def _parse_beats(section_text: str) -> list[ArgumentBeatClaim]:
    beats: list[ArgumentBeatClaim] = []
    for block in _extract_blocks(section_text):
        beat_id = _extract_block_field(block, "beat_id")
        beat_name = _extract_block_field(block, "beat_name")
        if not beat_id or not beat_name:
            continue
        beats.append(
            ArgumentBeatClaim(
                beat_id=beat_id,
                beat_name=beat_name,
                goal=_extract_block_field(block, "goal"),
                claim_ids=_extract_csv_field(block, "claim_ids"),
                proof_anchor_ids=_extract_csv_field(block, "proof_anchor_ids"),
                counterargument_ids=_extract_csv_field(block, "counterargument_ids"),
                transition_note=_extract_block_field(block, "transition_note"),
            )
        )
    return beats


def _extract_named_section(text: str, header: str) -> str:
    lines = text.splitlines()
    capture = False
    section_lines: list[str] = []
    normalized_header = header.lower()

    for raw_line in lines:
        stripped = raw_line.strip()
        line_header_match = re.match(r"^([a-z_]+):\s*$", stripped, re.IGNORECASE)
        if line_header_match:
            candidate = line_header_match.group(1).lower()
            if capture and candidate in _SECTION_HEADERS:
                break
            if candidate == normalized_header:
                capture = True
                continue
        if capture:
            section_lines.append(raw_line)
    return "\n".join(section_lines).strip()


def _extract_blocks(section_text: str) -> list[str]:
    if not section_text.strip():
        return []
    return [block.strip() for block in re.split(r"---+", section_text) if block.strip()]


def _extract_field(text: str, field_name: str) -> str:
    pattern = rf"(?im)^{re.escape(field_name)}:[ \t]*(.*)$"
    match = re.search(pattern, text)
    if match:
        return match.group(1).strip()
    return ""


def _extract_block_field(text: str, field_name: str) -> str:
    return _extract_field(text, field_name)


def _extract_csv_field(text: str, field_name: str) -> list[str]:
    value = _extract_block_field(text, field_name)
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]
