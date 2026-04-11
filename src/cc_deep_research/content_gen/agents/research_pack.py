"""Research pack builder agent with search provider integration."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

from cc_deep_research.content_gen.agents._llm_utils import call_agent_llm_text
from cc_deep_research.content_gen.models import (
    AngleOption,
    BacklogItem,
    ResearchClaim,
    ResearchClaimType,
    ResearchConfidence,
    ResearchCounterpoint,
    ResearchFinding,
    ResearchFindingType,
    ResearchFlagType,
    ResearchPack,
    ResearchSeverity,
    ResearchSource,
    ResearchUncertaintyFlag,
    RetrievalBudget,
    RetrievalDecision,
    RetrievalMode,
    RetrievalPlan,
)
from cc_deep_research.content_gen.prompts import research_pack as prompts
from cc_deep_research.llm import LLMRouter
from cc_deep_research.models import QueryFamily, QueryProvenance, SearchOptions, SearchResultItem

if TYPE_CHECKING:
    from cc_deep_research.config import Config

logger = logging.getLogger(__name__)

AGENT_ID = "content_gen_research"

# ---------------------------------------------------------------------------
# Retrieval Planner
# ---------------------------------------------------------------------------


class RetrievalPlanner:
    """Adaptive retrieval planner that builds query plans based on content needs.

    Replaces the old fixed query-family builder with a planner that can vary
    depth and breadth intentionally. Decisions are driven by:
    - Proof requirements from the angle/item
    - Prior feedback and identified research gaps
    - Freshness needs
    - Contrarian/counterevidence coverage
    - Explicit budget constraints
    """

    # Core families that form the baseline retrieval set
    _CORE_FAMILIES: list[tuple[str, list[str], str]] = [
        ("proof", ["proof", "evidence", "benchmark"], "Quantitative evidence, studies, and data"),
        ("primary-source", ["primary_source", "official", "documentation"], "Official sources, reports, and documentation"),
        ("competitor", ["competitor", "examples", "framing"], "Competitor coverage and content framing"),
        ("contrarian", ["counterevidence", "myth", "limitations"], "Counterarguments, myths, and limitations"),
        ("freshness", ["freshness", "latest", "trends"], "Latest developments and trends"),
        ("practitioner-language", ["practitioner", "language", "workflow"], "Practitioner perspectives and language"),
    ]

    def __init__(
        self,
        item: BacklogItem,
        angle: AngleOption,
        *,
        budget: RetrievalBudget | None = None,
        feedback: str = "",
        research_gaps: list[str] | None = None,
        mode: RetrievalMode = RetrievalMode.BASELINE,
    ) -> None:
        self.item = item
        self.angle = angle
        self.budget = budget or RetrievalBudget()
        self.feedback = feedback
        self.research_gaps = research_gaps or []
        self.mode = mode
        self._seen_queries: set[str] = set()

    def build_plan(self) -> RetrievalPlan:
        """Build a complete retrieval plan based on item, angle, and context."""
        decisions: list[RetrievalDecision] = []
        coverage_notes: list[str] = []

        # Determine effective mode
        effective_mode = self._resolve_mode()
        if effective_mode == RetrievalMode.TARGETED and self.research_gaps:
            gap_decisions, gap_notes = self._build_targeted_queries()
            decisions.extend(gap_decisions)
            coverage_notes.extend(gap_notes)
        elif effective_mode == RetrievalMode.CONTRARIAN:
            contrarian_decisions, contrarian_notes = self._build_contrarian_queries()
            decisions.extend(contrarian_decisions)
            coverage_notes.extend(contrarian_notes)
        elif effective_mode == RetrievalMode.DEEP:
            deep_decisions, deep_notes = self._build_deep_queries()
            decisions.extend(deep_decisions)
            coverage_notes.extend(deep_notes)
        else:
            baseline_decisions, baseline_notes = self._build_baseline_queries()
            decisions.extend(baseline_decisions)
            coverage_notes.extend(baseline_notes)

        # Respect budget limits
        decisions = self._apply_budget_limits(decisions)

        # Sort by priority (higher first)
        decisions.sort(key=lambda d: d.priority, reverse=True)

        return RetrievalPlan(
            decisions=decisions,
            budget=self.budget,
            mode=effective_mode,
            research_hypotheses=self._extract_hypotheses(),
            coverage_notes=coverage_notes,
            is_complete=len(decisions) > 0,
        )

    def _resolve_mode(self) -> RetrievalMode:
        """Determine the effective retrieval mode based on context."""
        # Explicit feedback indicating contrarian/coverage needs
        if self.feedback:
            feedback_lower = self.feedback.lower()
            if any(
                word in feedback_lower
                for word in ["contrarian", "counterevidence", "pushback", "alternative view"]
            ):
                return RetrievalMode.CONTRARIAN
            if any(
                word in feedback_lower for word in ["gap", "missing", "weak evidence", "unsupported"]
            ):
                return RetrievalMode.TARGETED
            if any(word in feedback_lower for word in ["deeper", "more evidence", "expand"]):
                return RetrievalMode.DEEP

        # Research gaps from quality evaluation
        if self.research_gaps:
            return RetrievalMode.TARGETED

        return self.mode

    def _extract_hypotheses(self) -> list[str]:
        """Extract research hypotheses from opportunity brief if available."""
        return []

    def _build_baseline_queries(self) -> tuple[list[RetrievalDecision], list[str]]:
        """Build the standard 6-family baseline query set."""
        decisions: list[RetrievalDecision] = []
        notes: list[str] = []

        subject = self._subject()
        audience = self._audience()
        problem = self._problem()
        current_year = _current_calendar_year()

        for idx, (family, intent_tags, rationale) in enumerate(self._CORE_FAMILIES):
            query = self._build_family_query(family, subject, audience, problem, current_year)
            if query:
                decisions.append(
                    RetrievalDecision(
                        family=family,
                        intent_tags=intent_tags,
                        query=query,
                        mode=RetrievalMode.BASELINE,
                        rationale=rationale,
                        priority=5 if family == "proof" else 3,
                    )
                )
                notes.append(f"{family}: {query[:50]}...")

        return decisions, notes

    def _build_targeted_queries(
        self,
    ) -> tuple[list[RetrievalDecision], list[str]]:
        """Build targeted queries addressing specific research gaps."""
        decisions: list[RetrievalDecision] = []
        notes: list[str] = []

        subject = self._subject()
        audience = self._audience()
        problem = self._problem()
        current_year = _current_calendar_year()

        # Always include baseline proof query for grounding
        proof_query = self._build_family_query("proof", subject, audience, problem, current_year)
        if proof_query:
            decisions.append(
                RetrievalDecision(
                    family="proof",
                    intent_tags=["proof", "evidence", "benchmark"],
                    query=proof_query,
                    mode=RetrievalMode.TARGETED,
                    rationale="Primary evidence for the core claim",
                    priority=10,
                )
            )

        # Build targeted queries for each gap
        for gap in self.research_gaps[:3]:  # Limit to 3 gap queries
            gap_query = f"{subject} {gap} {audience}".strip()
            decisions.append(
                RetrievalDecision(
                    family="targeted-gap",
                    intent_tags=["gap-filling", "specific evidence"],
                    query=gap_query,
                    mode=RetrievalMode.TARGETED,
                    rationale=f"Addressing research gap: {gap}",
                    priority=8,
                )
            )
            notes.append(f"gap: {gap_query[:50]}...")

        # Add freshness for recency if gaps mention "current" or "recent"
        if any(word in gap.lower() for gap in self.research_gaps for word in ["current", "recent", "latest"]):
            fresh_query = self._build_family_query("freshness", subject, audience, problem, current_year)
            if fresh_query:
                decisions.append(
                    RetrievalDecision(
                        family="freshness",
                        intent_tags=["freshness", "latest", "trends"],
                        query=fresh_query,
                        mode=RetrievalMode.TARGETED,
                        rationale="Recency-required gap query",
                        priority=6,
                    )
                )

        return decisions, notes

    def _build_contrarian_queries(
        self,
    ) -> tuple[list[RetrievalDecision], list[str]]:
        """Build queries emphasizing contrarian and counterevidence coverage."""
        decisions: list[RetrievalDecision] = []
        notes: list[str] = []

        subject = self._subject()
        audience = self._audience()
        problem = self._problem()
        current_year = _current_calendar_year()

        # Lead with contrarian coverage
        contra_query = self._build_family_query("contrarian", subject, audience, problem, current_year)
        if contra_query:
            decisions.append(
                RetrievalDecision(
                    family="contrarian",
                    intent_tags=["counterevidence", "myth", "limitations"],
                    query=contra_query,
                    mode=RetrievalMode.CONTRARIAN,
                    rationale="Primary contrarian and counterevidence search",
                    priority=10,
                )
            )
            notes.append(f"contrarian: {contra_query[:50]}...")

        # Include myth-busting variant
        myth_query = f"{subject} {problem or audience} myth misconception wrong belief".strip()
        if myth_query:
            decisions.append(
                RetrievalDecision(
                    family="myth-busting",
                    intent_tags=["myth", "misconception", "correction"],
                    query=myth_query,
                    mode=RetrievalMode.CONTRARIAN,
                    rationale="Myth and misconception coverage",
                    priority=9,
                )
            )

        # Add proof for balance
        proof_query = self._build_family_query("proof", subject, audience, problem, current_year)
        if proof_query:
            decisions.append(
                RetrievalDecision(
                    family="proof",
                    intent_tags=["proof", "evidence", "benchmark"],
                    query=proof_query,
                    mode=RetrievalMode.CONTRARIAN,
                    rationale="Balancing evidence alongside contrarian view",
                    priority=7,
                )
            )

        # Practitioner perspective
        pract_query = self._build_family_query("practitioner-language", subject, audience, problem, current_year)
        if pract_query:
            decisions.append(
                RetrievalDecision(
                    family="practitioner-language",
                    intent_tags=["practitioner", "language", "workflow"],
                    query=pract_query,
                    mode=RetrievalMode.CONTRARIAN,
                    rationale="Real-world practitioner language",
                    priority=5,
                )
            )

        return decisions, notes

    def _build_deep_queries(self) -> tuple[list[RetrievalDecision], list[str]]:
        """Build expanded query set for deep research coverage."""
        decisions: list[RetrievalDecision] = []
        notes: list[str] = []

        subject = self._subject()
        audience = self._audience()
        problem = self._problem()
        current_year = _current_calendar_year()

        # All baseline families first
        for idx, (family, intent_tags, rationale) in enumerate(self._CORE_FAMILIES):
            query = self._build_family_query(family, subject, audience, problem, current_year)
            if query:
                decisions.append(
                    RetrievalDecision(
                        family=family,
                        intent_tags=intent_tags,
                        query=query,
                        mode=RetrievalMode.DEEP,
                        rationale=f"Deep: {rationale}",
                        priority=5 if family == "proof" else 3,
                    )
                )

        # Add expanded variants for key families
        # More specific proof variants
        proof_variants = [
            f"{subject} {problem} case study data",
            f"{subject} {audience} benchmark statistics",
        ]
        for variant in proof_variants[:2]:
            if variant and self._is_unique_query(variant):
                decisions.append(
                    RetrievalDecision(
                        family="proof-expanded",
                        intent_tags=["proof", "evidence", "expanded"],
                        query=variant,
                        mode=RetrievalMode.DEEP,
                        rationale=f"Deep expanded: {variant[:40]}...",
                        priority=4,
                    )
                )

        # Practitioner depth
        pract_query = self._build_family_query("practitioner-language", subject, audience, problem, current_year)
        if pract_query:
            # Add workflow deep-dive
            decisions.append(
                RetrievalDecision(
                    family="practitioner-workflow",
                    intent_tags=["practitioner", "workflow", "process"],
                    query=f"{audience} {problem or subject} workflow process step by step".strip(),
                    mode=RetrievalMode.DEEP,
                    rationale="Deep practitioner workflow coverage",
                    priority=3,
                )
            )

        return decisions, notes

    def _build_family_query(
        self, family: str, subject: str, audience: str, problem: str, current_year: int
    ) -> str:
        """Build the query string for a specific family."""
        if family == "proof":
            return _join_terms(subject, problem, "evidence study benchmark data")
        elif family == "primary-source":
            return _join_terms(subject, "official report documentation transcript filing")
        elif family == "competitor":
            return _join_terms(subject, audience, "competitor example teardown case study")
        elif family == "contrarian":
            return _join_terms(subject, "myth critique limitation counterexample")
        elif family == "freshness":
            return _join_terms(subject, audience, str(current_year), "latest trends update")
        elif family == "practitioner-language":
            return _join_terms(audience, problem or subject, "practitioner playbook operator lessons")
        return ""

    def _is_unique_query(self, query: str) -> bool:
        """Check if query is not a duplicate."""
        normalized = " ".join(query.split()).casefold()
        if normalized in self._seen_queries:
            return False
        self._seen_queries.add(normalized)
        return True

    def _apply_budget_limits(self, decisions: list[RetrievalDecision]) -> list[RetrievalDecision]:
        """Apply budget constraints to the decision list."""
        if self.budget.max_queries and len(decisions) > self.budget.max_queries:
            # Keep highest priority decisions
            decisions = sorted(decisions, key=lambda d: d.priority, reverse=True)[: self.budget.max_queries]
        return decisions

    def _subject(self) -> str:
        return _first_non_empty(
            self.angle.core_promise,
            self.item.idea,
            self.angle.primary_takeaway,
            self.angle.viewer_problem,
            self.item.problem,
        )

    def _audience(self) -> str:
        return _first_non_empty(self.angle.target_audience, self.item.audience)

    def _problem(self) -> str:
        return _first_non_empty(self.angle.viewer_problem, self.item.problem)


def _maybe_set_degraded(
    pack: ResearchPack,
    text: str,
) -> None:
    """Set degraded state on ResearchPack if output is partial or empty."""
    if not text:
        pack.is_degraded = True
        pack.degradation_reason = "blank LLM response after retry"
        return

    structured_fields = [pack.findings, pack.claims, pack.counterpoints, pack.uncertainty_flags]
    non_empty = [f for f in structured_fields if f]
    empty = [f for f in structured_fields if not f]

    if not non_empty:
        pack.is_degraded = True
        pack.degradation_reason = "parser produced zero usable records"
        return

    if empty:
        pack.is_degraded = True
        field_names = [f.__class__.__name__ for f in empty]
        pack.degradation_reason = f"parser produced partial records; missing: {', '.join(field_names)}"

_LEGACY_LIST_FIELDS = [
    "audience_insights",
    "competitor_observations",
    "key_facts",
    "proof_points",
    "examples",
    "case_studies",
    "gaps_to_exploit",
    "assets_needed",
    "claims_requiring_verification",
    "unsafe_or_uncertain_claims",
]

_ALL_SECTION_HEADERS = (
    "findings",
    "claims",
    "counterpoints",
    "uncertainty_flags",
    "assets_needed",
    *_LEGACY_LIST_FIELDS,
    "research_stop_reason",
)


class ResearchPackAgent:
    """Build a compact research pack using search providers and LLM synthesis."""

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
        return await call_agent_llm_text(
            router=self._router,
            agent_id=AGENT_ID,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            workflow_name="research pack workflow",
            cli_command="content-gen research",
            logger=logger,
            allow_blank=True,
        )

    async def build(
        self,
        item: BacklogItem,
        angle: AngleOption,
        *,
        max_queries: int | None = None,
        feedback: str = "",
        research_gaps: list[str] | None = None,
    ) -> ResearchPack:
        budget = RetrievalBudget(max_queries=max_queries or self._config.content_gen.research_max_queries)
        search_context, supporting_sources = await self._run_searches(
            item, angle, budget=budget, feedback=feedback, research_gaps=research_gaps
        )

        system = prompts.SYNTHESIS_SYSTEM
        user = prompts.synthesis_user(item, angle, search_context, feedback=feedback)
        text = await self._call_llm(system, user, temperature=0.3)

        pack = _parse_research_pack(
            text,
            item.idea_id,
            angle.angle_id,
            supporting_sources=supporting_sources,
        )

        # Detect and record degraded state
        _maybe_set_degraded(pack, text)

        return pack

    async def _run_searches(
        self,
        item: BacklogItem,
        angle: AngleOption,
        *,
        budget: RetrievalBudget,
        feedback: str = "",
        research_gaps: list[str] | None = None,
    ) -> tuple[str, list[ResearchSource]]:
        planner = RetrievalPlanner(
            item,
            angle,
            budget=budget,
            feedback=feedback,
            research_gaps=research_gaps,
        )
        plan = planner.build_plan()

        if not plan.decisions:
            return "No search queries generated.", []

        try:
            providers = self._get_providers()
        except Exception:
            logger.warning("Could not initialize search providers; skipping search")
            return "Search providers unavailable.", []

        max_results = budget.max_results_per_query
        opts = SearchOptions(max_results=max_results)
        sources_by_url: dict[str, ResearchSource] = {}
        next_source_index = 1

        for decision in plan.decisions:
            # Early termination if budget exhausted
            if len(sources_by_url) >= budget.max_sources:
                break
            if budget.stop_if_sources_seen and len(sources_by_url) >= budget.stop_if_sources_seen:
                break

            query_plan = QueryFamily(
                query=decision.query,
                family=decision.family,
                intent_tags=decision.intent_tags,
            )

            for provider in providers:
                if len(sources_by_url) >= budget.max_sources:
                    break

                try:
                    result = await provider.search(decision.query, opts)
                except Exception:
                    logger.debug("Search query '%s' failed", decision.query, exc_info=True)
                    continue

                for item_result in result.results[:3]:
                    if len(sources_by_url) >= budget.max_sources:
                        break

                    existing = sources_by_url.get(item_result.url)
                    if existing is None:
                        source = _source_from_search_result(
                            item_result,
                            query_plan=query_plan,
                            provider_name=result.provider,
                            source_id=f"src_{next_source_index:02d}",
                        )
                        sources_by_url[item_result.url] = source
                        next_source_index += 1
                    else:
                        _merge_query_context(existing, item_result, query_plan=query_plan)

        supporting_sources = list(sources_by_url.values())
        if not supporting_sources:
            return "No search results found.", []
        return _render_source_catalog(supporting_sources), supporting_sources

    def _get_providers(self) -> list:
        from cc_deep_research.providers import resolve_provider_specs
        from cc_deep_research.providers.factory import build_search_providers

        specs = resolve_provider_specs(self._config)
        providers, _ = build_search_providers(self._config, specs)
        return providers


def _build_search_queries(item: BacklogItem, angle: AngleOption) -> list[QueryFamily]:
    subject = _first_non_empty(
        angle.core_promise,
        item.idea,
        angle.primary_takeaway,
        angle.viewer_problem,
        item.problem,
    )
    audience = _first_non_empty(angle.target_audience, item.audience)
    problem = _first_non_empty(angle.viewer_problem, item.problem)
    if not subject:
        return []

    query_plans: list[QueryFamily] = []
    seen_queries: set[str] = set()

    _append_query_plan(
        query_plans,
        seen_queries,
        family="proof",
        intent_tags=["proof", "evidence", "benchmark"],
        query=_join_terms(subject, problem, "evidence study benchmark data"),
    )
    _append_query_plan(
        query_plans,
        seen_queries,
        family="primary-source",
        intent_tags=["primary_source", "official", "documentation"],
        query=_join_terms(subject, "official report documentation transcript filing"),
    )
    _append_query_plan(
        query_plans,
        seen_queries,
        family="competitor",
        intent_tags=["competitor", "examples", "framing"],
        query=_join_terms(subject, audience, "competitor example teardown case study"),
    )
    _append_query_plan(
        query_plans,
        seen_queries,
        family="contrarian",
        intent_tags=["counterevidence", "myth", "limitations"],
        query=_join_terms(subject, "myth critique limitation counterexample"),
    )
    _append_query_plan(
        query_plans,
        seen_queries,
        family="freshness",
        intent_tags=["freshness", "latest", "trends"],
        query=_join_terms(subject, audience, str(_current_calendar_year()), "latest trends update"),
    )
    _append_query_plan(
        query_plans,
        seen_queries,
        family="practitioner-language",
        intent_tags=["practitioner", "language", "workflow"],
        query=_join_terms(audience, problem or subject, "practitioner playbook operator lessons"),
    )

    return query_plans


def _append_query_plan(
    query_plans: list[QueryFamily],
    seen_queries: set[str],
    *,
    family: str,
    intent_tags: list[str],
    query: str,
) -> None:
    normalized_query = " ".join(query.split())
    if not normalized_query:
        return
    dedupe_key = normalized_query.casefold()
    if dedupe_key in seen_queries:
        return
    seen_queries.add(dedupe_key)
    query_plans.append(
        QueryFamily(
            query=normalized_query,
            family=family,
            intent_tags=intent_tags,
        )
    )


def _join_terms(*parts: str) -> str:
    cleaned_parts: list[str] = []
    seen_parts: set[str] = set()
    for part in parts:
        normalized = " ".join(str(part).split()).strip()
        if not normalized:
            continue
        dedupe_key = normalized.casefold()
        if dedupe_key in seen_parts:
            continue
        seen_parts.add(dedupe_key)
        cleaned_parts.append(normalized)
    return " ".join(cleaned_parts)


def _first_non_empty(*parts: str) -> str:
    for part in parts:
        normalized = " ".join(str(part).split()).strip()
        if normalized:
            return normalized
    return ""


def _current_calendar_year() -> int:
    return datetime.now().year


def _source_from_search_result(
    item: SearchResultItem,
    *,
    query_plan: QueryFamily,
    provider_name: str,
    source_id: str,
) -> ResearchSource:
    published_date = (
        str(item.source_metadata.get("published_date") or item.source_metadata.get("published") or "").strip()
        or None
    )
    provenance = list(item.query_provenance)
    if not provenance:
        provenance = [
            QueryProvenance(
                query=query_plan.query,
                family=query_plan.family,
                intent_tags=list(query_plan.intent_tags),
            )
        ]
    return ResearchSource(
        source_id=source_id,
        url=item.url,
        title=item.title,
        provider=provider_name,
        query=query_plan.query,
        query_family=query_plan.family,
        intent_tags=list(query_plan.intent_tags),
        published_date=published_date,
        snippet=(item.snippet or item.content or "")[:400],
        query_provenance=provenance,
        source_metadata=dict(item.source_metadata),
    )


def _merge_query_context(
    source: ResearchSource,
    item: SearchResultItem,
    *,
    query_plan: QueryFamily,
) -> None:
    existing_keys = {
        (entry.query, entry.family, tuple(entry.intent_tags))
        for entry in source.query_provenance
    }
    new_entries = list(item.query_provenance) or [
        QueryProvenance(
            query=query_plan.query,
            family=query_plan.family,
            intent_tags=list(query_plan.intent_tags),
        )
    ]
    for entry in new_entries:
        key = (entry.query, entry.family, tuple(entry.intent_tags))
        if key in existing_keys:
            continue
        source.query_provenance.append(entry)
        existing_keys.add(key)


def _render_source_catalog(sources: list[ResearchSource]) -> str:
    parts = ["Source Catalog:"]
    for source in sources:
        parts.append(
            "\n".join(
                [
                    f"[{source.source_id}]",
                    f"title: {source.title or 'Untitled source'}",
                    f"url: {source.url}",
                    f"provider: {source.provider or 'unknown'}",
                    f"query: {source.query or 'unknown'}",
                    f"query_family: {source.query_family or 'baseline'}",
                    f"published_date: {source.published_date or 'unknown'}",
                    f"snippet: {source.snippet or 'No snippet available'}",
                ]
            )
        )
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_research_pack(
    text: str,
    idea_id: str,
    angle_id: str,
    *,
    supporting_sources: list[ResearchSource] | None = None,
) -> ResearchPack:
    """Parse structured research sections with legacy fallback support."""

    data: dict[str, Any] = {
        "idea_id": idea_id,
        "angle_id": angle_id,
        "supporting_sources": list(supporting_sources or []),
        "findings": _parse_findings(_extract_named_section(text, "findings")),
        "claims": _parse_claims(_extract_named_section(text, "claims")),
        "counterpoints": _parse_counterpoints(_extract_named_section(text, "counterpoints")),
        "uncertainty_flags": _parse_uncertainty_flags(_extract_named_section(text, "uncertainty_flags")),
        "assets_needed": _extract_list_section(text, "assets_needed"),
        "research_stop_reason": _extract_field(text, "research_stop_reason"),
    }
    for field in _LEGACY_LIST_FIELDS:
        if field == "assets_needed":
            continue
        data[field] = _extract_list_section(text, field)
    return ResearchPack(**data)


def _parse_findings(section_text: str) -> list[ResearchFinding]:
    findings: list[ResearchFinding] = []
    for block in _extract_blocks(section_text):
        summary = _extract_block_field(block, "summary")
        if not summary:
            continue
        findings.append(
            ResearchFinding(
                finding_type=_normalize_finding_type(_extract_block_field(block, "finding_type")),
                summary=summary,
                source_ids=_extract_csv_field(block, "source_ids"),
                confidence=_normalize_confidence(_extract_block_field(block, "confidence")),
                evidence_note=_extract_block_field(block, "evidence_note"),
            )
        )
    return findings


def _parse_claims(section_text: str) -> list[ResearchClaim]:
    claims: list[ResearchClaim] = []
    for block in _extract_blocks(section_text):
        claim = _extract_block_field(block, "claim")
        if not claim:
            continue
        claims.append(
            ResearchClaim(
                claim_type=_normalize_claim_type(_extract_block_field(block, "claim_type")),
                claim=claim,
                source_ids=_extract_csv_field(block, "source_ids"),
                confidence=_normalize_confidence(_extract_block_field(block, "confidence")),
                mechanism=_extract_block_field(block, "mechanism"),
            )
        )
    return claims


def _parse_counterpoints(section_text: str) -> list[ResearchCounterpoint]:
    counterpoints: list[ResearchCounterpoint] = []
    for block in _extract_blocks(section_text):
        summary = _extract_block_field(block, "summary")
        if not summary:
            continue
        counterpoints.append(
            ResearchCounterpoint(
                summary=summary,
                why_it_matters=_extract_block_field(block, "why_it_matters"),
                source_ids=_extract_csv_field(block, "source_ids"),
                confidence=_normalize_confidence(_extract_block_field(block, "confidence")),
            )
        )
    return counterpoints


def _parse_uncertainty_flags(section_text: str) -> list[ResearchUncertaintyFlag]:
    flags: list[ResearchUncertaintyFlag] = []
    for block in _extract_blocks(section_text):
        claim = _extract_block_field(block, "claim")
        if not claim:
            continue
        flags.append(
            ResearchUncertaintyFlag(
                flag_type=_normalize_flag_type(_extract_block_field(block, "flag_type")),
                claim=claim,
                reason=_extract_block_field(block, "reason"),
                severity=_normalize_severity(_extract_block_field(block, "severity")),
                source_ids=_extract_csv_field(block, "source_ids"),
            )
        )
    return flags


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
            if capture and candidate in {name.lower() for name in _ALL_SECTION_HEADERS}:
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
    pattern = rf"{re.escape(field_name)}:\s*(.+?)(?:\n|$)"
    match = re.search(pattern, text, re.IGNORECASE)
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


def _extract_list_section(text: str, header: str) -> list[str]:
    items: list[str] = []
    in_section = False
    normalized_header = header.lower().replace("_", " ")
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.lower().replace("_", " ") == f"{normalized_header}:":
            in_section = True
            continue
        if in_section:
            if stripped.startswith("- ") or stripped.startswith("* "):
                items.append(stripped[2:].strip())
            elif stripped and not stripped.startswith("-") and not stripped.startswith("*"):
                break
    return items


def _normalize_confidence(value: str) -> ResearchConfidence:
    normalized = value.strip().lower()
    if normalized in {member.value for member in ResearchConfidence}:
        return ResearchConfidence(normalized)
    return ResearchConfidence.UNKNOWN


def _normalize_finding_type(value: str) -> ResearchFindingType:
    normalized = value.strip().lower()
    if normalized in {member.value for member in ResearchFindingType}:
        return ResearchFindingType(normalized)
    return ResearchFindingType.AUDIENCE_INSIGHT


def _normalize_claim_type(value: str) -> ResearchClaimType:
    normalized = value.strip().lower()
    if normalized in {member.value for member in ResearchClaimType}:
        return ResearchClaimType(normalized)
    return ResearchClaimType.KEY_FACT


def _normalize_flag_type(value: str) -> ResearchFlagType:
    normalized = value.strip().lower()
    if normalized in {member.value for member in ResearchFlagType}:
        return ResearchFlagType(normalized)
    return ResearchFlagType.VERIFICATION_REQUIRED


def _normalize_severity(value: str) -> ResearchSeverity:
    normalized = value.strip().lower()
    if normalized in {member.value for member in ResearchSeverity}:
        return ResearchSeverity(normalized)
    return ResearchSeverity.MEDIUM
