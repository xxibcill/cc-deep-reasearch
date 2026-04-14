"""Batch triage agent for superuser backlog analysis."""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from cc_deep_research.content_gen.agents import batch_analysis
from cc_deep_research.content_gen.agents._llm_utils import call_agent_llm_text
from cc_deep_research.content_gen.backlog_service import BacklogService
from cc_deep_research.content_gen.models import BacklogItem, TriageOperation
from cc_deep_research.content_gen.prompts import backlog_triage as prompts
from cc_deep_research.llm import LLMRouter

if TYPE_CHECKING:
    from cc_deep_research.config import Config

logger = logging.getLogger(__name__)

AGENT_ID = "content_gen_backlog_triage"

# Fields that can be enriched on sparse items
ENRICHABLE_FIELDS = frozenset(
    {
        "why_now",
        "potential_hook",
        "evidence",
        "proof_gap_note",
        "genericity_risk",
    }
)

# Fields that can be reframed
REFRAME_ELIGIBLE_FIELDS = frozenset(
    {
        "idea",
        "problem",
        "audience",
        "potential_hook",
    }
)

SUPPORTED_UPDATE_FIELDS = frozenset(
    {
        "idea",
        "category",
        "audience",
        "problem",
        "source",
        "why_now",
        "potential_hook",
        "content_type",
        "evidence",
        "risk_level",
        "status",
        "selection_reasoning",
        "genericity_risk",
        "proof_gap_note",
    }
)


class BatchTriageAgent:
    """Batch triage agent for superuser backlog cleanup and enrichment."""

    def __init__(self, config: Config | None = None) -> None:
        from cc_deep_research.llm.registry import LLMRouteRegistry

        if config is None:
            from cc_deep_research.config import load_config

            config = load_config()

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
        return await call_agent_llm_text(
            router=self._router,
            agent_id=AGENT_ID,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            workflow_name="backlog triage",
            cli_command="content-gen backlog-triage",
            logger=logger,
            allow_blank=False,
        )

    async def respond(
        self,
        backlog_items: list[BacklogItem],
        *,
        strategy: dict[str, Any] | None = None,
    ) -> TriageResponseOutput:
        """Generate batch triage proposals for the backlog.

        Runs heuristic pre-processing first, then uses LLM to refine proposals.

        Args:
            backlog_items: Current backlog snapshot
            strategy: Optional strategy context

        Returns:
            TriageResponseOutput with proposals and metadata
        """
        # Run heuristic pre-processing
        analysis_context = self._run_batch_analysis(backlog_items)

        system = prompts.BACKLOG_TRIAGE_SYSTEM
        user = prompts.build_triage_user(
            backlog_items=backlog_items,
            strategy=strategy,
            analysis_context=analysis_context,
        )

        try:
            text = await self._call_llm(system, user, temperature=0.3)
            parsed = _parse_triage_response(text)

            valid_ids = {item.idea_id for item in backlog_items}
            validated_mentioned = [
                idea_id for idea_id in parsed.get("mentioned_idea_ids", []) if idea_id in valid_ids
            ]

            warnings = list(parsed.get("warnings", []))
            proposals = _validate_proposals(
                parsed.get("proposals", []),
                backlog_items,
            )

            return TriageResponseOutput(
                reply_markdown=parsed.get("reply_markdown", "Analysis complete."),
                proposals=proposals,
                warnings=warnings,
                mentioned_idea_ids=validated_mentioned,
            )

        except Exception as exc:
            logger.warning("Backlog triage LLM call failed: %s", exc)
            return TriageResponseOutput(
                reply_markdown=("I had trouble analyzing the backlog. Feel free to try again."),
                proposals=[],
                warnings=[f"LLM call failed: {exc}"],
                mentioned_idea_ids=[],
            )

    def _run_batch_analysis(
        self,
        items: list[BacklogItem],
    ) -> dict[str, Any]:
        """Run heuristic pre-processing for batch analysis."""
        # Find exact and near duplicates
        exact_dupes = batch_analysis.find_exact_duplicates(items)
        near_dupes = batch_analysis.find_near_duplicates(items)

        # Find sparse items needing enrichment
        sparse_items = batch_analysis.find_sparse_items(items)

        # Gap analysis
        gaps = batch_analysis.analyze_gaps(items)

        # Theme clusters
        theme_clusters = batch_analysis.cluster_by_theme(items)

        return {
            "duplicate_candidates": [
                {
                    "idea_id_a": d.idea_id_a,
                    "idea_id_b": d.idea_id_b,
                    "score": d.score,
                    "preferred_id": d.preferred_id,
                }
                for d in exact_dupes + near_dupes
            ],
            "sparse_items": [
                {
                    "idea_id": s.idea_id,
                    "score": s.score,
                    "missing_fields": s.missing_fields,
                    "weak_fields": s.weak_fields,
                }
                for s in sparse_items
            ],
            "gaps": [
                {
                    "gap_type": g.gap_type,
                    "description": g.description,
                    "affected_idea_ids": g.affected_idea_ids,
                    "suggestion": g.suggestion,
                }
                for g in gaps
            ],
            "theme_clusters": {k: len(v) for k, v in theme_clusters.items()},
        }


class TriageResponseOutput(BaseModel):
    """Structured output from the triage agent."""

    reply_markdown: str
    proposals: list[TriageOperation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    mentioned_idea_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------


def _extract_json_from_text(text: str) -> dict[str, Any] | None:
    """Extract JSON object from text, handling code fences and partial output."""
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fence_pattern = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL | re.IGNORECASE)
    for match in fence_pattern.finditer(text):
        candidate = match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    json_start = text.find("{")
    if json_start != -1:
        depth = 0
        for i, ch in enumerate(text[json_start:], start=json_start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[json_start : i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break

    return None


def _parse_triage_response(text: str) -> dict[str, Any]:
    """Parse LLM output into a dict, with graceful fallback."""
    parsed = _extract_json_from_text(text)
    if parsed is None:
        return {
            "reply_markdown": text.strip()[:500] if text.strip() else "Analysis complete.",
            "proposals": [],
            "warnings": ["Failed to parse structured output from LLM"],
            "mentioned_idea_ids": [],
        }

    raw_reply = str(parsed.get("reply_markdown", "") or "Analysis complete.")
    result: dict[str, Any] = {
        "reply_markdown": raw_reply[:1000],
        "proposals": list(parsed.get("proposals", [])),
        "warnings": list(parsed.get("warnings", [])),
        "mentioned_idea_ids": list(parsed.get("mentioned_idea_ids", [])),
    }

    return result


# ---------------------------------------------------------------------------
# Proposal validation
# ---------------------------------------------------------------------------


def _validate_proposals(
    proposals: list[dict[str, Any]],
    backlog_items: list[BacklogItem],
) -> list[TriageOperation]:
    """Validate and normalize proposals from LLM output."""
    validated: list[TriageOperation] = []
    existing_ids = {item.idea_id for item in backlog_items}
    valid_kinds = {
        "batch_enrich",
        "batch_reframe",
        "dedupe_recommendation",
        "archive_recommendation",
        "priority_recommendation",
    }

    for proposal in proposals:
        if not isinstance(proposal, dict):
            continue

        kind = proposal.get("kind", "")
        if kind not in valid_kinds:
            continue

        idea_ids = [
            iid
            for iid in proposal.get("idea_ids", [])
            if isinstance(iid, str) and iid in existing_ids
        ]
        if not idea_ids:
            continue

        fields = _sanitize_fields(proposal.get("fields", {}))
        preferred = proposal.get("preferred_idea_id")
        if preferred and preferred not in existing_ids:
            preferred = None

        validated.append(
            TriageOperation(
                kind=kind,  # type: ignore[arg-type]
                idea_ids=idea_ids,
                reason=str(proposal.get("reason", ""))[:500],
                fields=fields,
                preferred_idea_id=preferred,
            )
        )

    return validated


def _sanitize_fields(fields: dict[str, Any]) -> dict[str, Any]:
    """Remove invalid fields from a proposal."""
    return {k: str(v)[:2000] for k, v in fields.items() if k in SUPPORTED_UPDATE_FIELDS and v}


# ---------------------------------------------------------------------------
# Apply helpers
# ---------------------------------------------------------------------------


def build_apply_operations(
    operations: list[dict[str, Any]],
    backlog_items: list[BacklogItem],
) -> tuple[list[TriageOperation], list[str]]:
    """Validate client-submitted triage operations.

    Returns validated operations and a list of error messages.
    """
    validated: list[TriageOperation] = []
    errors: list[str] = []
    existing_ids = {item.idea_id for item in backlog_items}
    valid_kinds = {
        "batch_enrich",
        "batch_reframe",
        "dedupe_recommendation",
        "archive_recommendation",
        "priority_recommendation",
    }

    for index, op in enumerate(operations, start=1):
        if not isinstance(op, dict):
            errors.append(f"Operation {index}: invalid payload")
            continue

        kind = op.get("kind", "")
        if kind not in valid_kinds:
            errors.append(f"Operation {index}: unknown operation kind '{kind}'")
            continue

        idea_ids = [
            iid for iid in op.get("idea_ids", []) if isinstance(iid, str) and iid in existing_ids
        ]
        if not idea_ids:
            errors.append(f"Operation {index}: no valid idea_ids found")
            continue

        fields = _sanitize_fields(op.get("fields", {}))
        preferred = op.get("preferred_idea_id")
        if preferred and preferred not in existing_ids:
            errors.append(f"Operation {index}: preferred_idea_id '{preferred}' not found")
            continue

        validated.append(
            TriageOperation(
                kind=kind,  # type: ignore[arg-type]
                idea_ids=idea_ids,
                reason=str(op.get("reason", ""))[:500],
                fields=fields,
                preferred_idea_id=preferred,
            )
        )

    return validated, errors


async def apply_triage_operations(
    operations: list[TriageOperation],
    service: BacklogService,
) -> tuple[int, list[BacklogItem], list[str]]:
    """Apply validated triage operations through BacklogService.

    Args:
        operations: List of validated triage operations
        service: BacklogService instance

    Returns:
        Tuple of (applied_count, list of modified items, list of errors)
    """
    applied = 0
    items: list[BacklogItem] = []
    errors: list[str] = []

    # Cache backlog items once before the loop to avoid O(n) lookups per operation
    backlog_items_by_id = {item.idea_id: item for item in service.load().items}

    for op in operations:
        try:
            if op.kind == "archive_recommendation":
                for idea_id in op.idea_ids:
                    archived = service.archive_item(idea_id)
                    if archived:
                        applied += 1
                        items.append(archived)
                    else:
                        errors.append(f"archive {idea_id}: item not found")

            elif op.kind == "priority_recommendation":
                if "priority_score" in op.fields or "latest_recommendation" in op.fields:
                    for idea_id in op.idea_ids:
                        updated = service.update_item(idea_id, op.fields)
                        if updated:
                            applied += 1
                            items.append(updated)
                        else:
                            errors.append(f"priority {idea_id}: item not found")

            elif op.kind in ("batch_enrich", "batch_reframe"):
                # Only apply to sparse/weak items, not overwriting strong operator content
                for idea_id in op.idea_ids:
                    target = backlog_items_by_id.get(idea_id)
                    if target is None:
                        errors.append(f"{op.kind} {idea_id}: item not found")
                        continue

                    # Skip if item has strong operator content in the same fields
                    if op.kind == "batch_enrich":
                        if _is_enriched(target):
                            continue
                    elif op.kind == "batch_reframe":
                        if _is_well_reframed(target):
                            continue

                    updated = service.update_item(idea_id, op.fields)
                    if updated:
                        applied += 1
                        items.append(updated)

            elif op.kind == "dedupe_recommendation":
                if op.preferred_idea_id and len(op.idea_ids) > 1:
                    # Archive all but the preferred item
                    survivors = set(op.idea_ids) - {op.preferred_idea_id}
                    for idea_id in survivors:
                        archived = service.archive_item(idea_id)
                        if archived:
                            applied += 1
                            items.append(archived)
                        else:
                            errors.append(f"dedupe archive {idea_id}: item not found")

        except Exception as exc:
            errors.append(f"{op.kind}: {exc}")

    return applied, items, errors


def _is_enriched(item: BacklogItem) -> bool:
    """Check if an item already has strong enrichment fields."""
    strong_fields = ["evidence", "why_now", "potential_hook"]
    non_empty = sum(1 for f in strong_fields if getattr(item, f, ""))
    return non_empty >= 2


def _is_well_reframed(item: BacklogItem) -> bool:
    """Check if an item already has strong reframing (idea + problem + hook)."""
    strong_fields = ["idea", "problem", "potential_hook"]
    non_empty = sum(1 for f in strong_fields if getattr(item, f, ""))
    return non_empty >= 2

