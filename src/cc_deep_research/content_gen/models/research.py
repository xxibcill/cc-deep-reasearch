"""Research pack and evidence models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from cc_deep_research.models.search import QueryProvenance

from .shared import (
    ClaimStatus,
    ClaimTraceStage,
    ClaimTraceStatus,
    EvidenceDirectness,
    FactRiskDecision,
    ResearchClaimType,
    ResearchConfidence,
    ResearchDepthTier,
    ResearchFindingType,
    ResearchFlagType,
    ResearchSeverity,
    RetrievalMode,
    SourceAuthority,
    SourceFreshness,
)


class ScriptClaimStatement(BaseModel):
    """A single claim statement extracted from a script for tracing."""

    claim_id: str = Field(description="Unique claim identifier")
    claim: str = Field(description="The claim text")
    beat_id: str = Field(default="", description="Beat this claim belongs to")
    sourcing_required: bool = True


class ClaimTraceEntry(BaseModel):
    """Single entry in the claim trace ledger."""

    claim_id: str
    claim: str
    status: ClaimTraceStatus = ClaimTraceStatus.PENDING
    source_ids: list[str] = Field(default_factory=list)
    stage: ClaimTraceStage = ClaimTraceStage.RESEARCH_PACK
    evidence_strength: float = 0.0
    notes: str = ""


class ClaimTraceLedger(BaseModel):
    """Ledger tracking all claims and their evidence status through the pipeline."""

    idea_id: str = ""
    entries: list[ClaimTraceEntry] = Field(default_factory=list)
    unverified_claims: list[str] = Field(default_factory=list)
    weak_claims: list[str] = Field(default_factory=list)

    def supported_claims(self) -> list[ClaimTraceEntry]:
        """Return claims with SUPPORTED status."""
        return [e for e in self.entries if e.status == ClaimTraceStatus.SUPPORTED]

    def pending_claims(self) -> list[ClaimTraceEntry]:
        """Return claims with PENDING status."""
        return [e for e in self.entries if e.status == ClaimTraceStatus.PENDING]

    def unsupported_claims(self) -> list[ClaimTraceEntry]:
        """Return claims with UNSUPPORTED status."""
        return [e for e in self.entries if e.status == ClaimTraceStatus.UNSUPPORTED]


class ResearchDepthRouting(BaseModel):
    """Routing decisions for research depth per claim cluster."""

    claim_cluster: str = ""
    depth_tier: ResearchDepthTier = ResearchDepthTier.STANDARD
    retrieval_mode: RetrievalMode = RetrievalMode.BASELINE
    max_sources: int = 10


class ResearchSource(BaseModel):
    """Research source with quality signals."""

    source_id: str = ""
    url: str = ""
    title: str = ""
    authority: SourceAuthority = SourceAuthority.MEDIUM
    directness: EvidenceDirectness = EvidenceDirectness.INDIRECT
    freshness: SourceFreshness = SourceFreshness.RECENT
    quality_rank: float = 0.0
    query_variation: str = ""
    provenance: list[QueryProvenance] = Field(default_factory=list)


class ResearchFinding(BaseModel):
    """A single research finding."""

    finding_id: str = ""
    finding: str = ""
    source_ids: list[str] = Field(default_factory=list)
    finding_type: ResearchFindingType = ResearchFindingType.FACTUAL
    confidence: ResearchConfidence = ResearchConfidence.MEDIUM


class ResearchClaim(BaseModel):
    """A claim supported by research."""

    claim_id: str = ""
    claim: str = ""
    source_ids: list[str] = Field(default_factory=list)
    claim_type: ResearchClaimType = ResearchClaimType.SAFE
    confidence: ResearchConfidence = ResearchConfidence.MEDIUM


class ResearchCounterpoint(BaseModel):
    """A counterpoint or objection to address."""

    counterpoint_id: str = ""
    counterpoint: str = ""
    source_ids: list[str] = Field(default_factory=list)
    response_strategy: str = ""


class ResearchUncertaintyFlag(BaseModel):
    """An uncertainty or risk flag on a claim."""

    flag_id: str = ""
    flag_type: ResearchFlagType = ResearchFlagType.VERIFICATION_REQUIRED
    claim: str = ""
    severity: ResearchSeverity = ResearchSeverity.MEDIUM
    notes: str = ""


class ResearchPack(BaseModel):
    """Output of the research stage."""

    idea_id: str = ""
    angle_id: str = ""
    research_mode: str = ""
    research_depth_routing: list[ResearchDepthRouting] = Field(default_factory=list)
    sources: list[ResearchSource] = Field(default_factory=list)
    findings: list[ResearchFinding] = Field(default_factory=list)
    claims: list[ResearchClaim] = Field(default_factory=list)
    counterpoints: list[ResearchCounterpoint] = Field(default_factory=list)
    uncertainty_flags: list[ResearchUncertaintyFlag] = Field(default_factory=list)
    assets_needed: list[str] = Field(default_factory=list)
    research_stop_reason: str = ""
    # Legacy claim fields (used for backward compatibility)
    claims_requiring_verification: list[str] = Field(default_factory=list)
    unsafe_or_uncertain_claims: list[str] = Field(default_factory=list)
    # P3-T3: Evidence gap tracking
    evidence_gaps: list[str] = Field(default_factory=list)
    # Claim ledger for trace
    claim_ledger: ClaimTraceLedger | None = None


class FactRiskGate(BaseModel):
    """Early gate decision based on fact-risk assessment."""

    idea_id: str = ""
    decision: str = ""
    claim_count: int = 0
    supported_claim_count: int = 0
    unsupported_claim_count: int = 0
    weak_claim_count: int = 0
    flagged_claims: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    is_safe_to_proceed: bool = False


class FactRiskGateResult(BaseModel):
    """Full output of the fact-risk gate stage."""

    gate: FactRiskGate | None = None
    is_gated: bool = False
    gating_reason: str = ""
    decision: FactRiskDecision = FactRiskDecision.PASS


class FactRiskGateOutput(BaseModel):
    """Wrapper for fact-risk gate result with metadata."""

    result: FactRiskGateResult | None = None
    idea_id: str = ""
    stage_name: str = "fact_risk_gate"


class ProgressiveQCIssue(BaseModel):
    """Quality issue detected before final QC, with first-seen stage."""

    issue_id: str = ""
    issue: str = ""
    severity: ResearchSeverity = ResearchSeverity.MEDIUM
    first_seen_stage: str = ""
    beat_id: str = ""


class ProgressiveQCCheckpoint(BaseModel):
    """QC checkpoint captured at a specific stage."""

    stage_name: str = ""
    passed: bool = True
    issues: list[str] = Field(default_factory=list)


class RetrievalDecision(BaseModel):
    """Single query decision from the retrieval planner."""

    family: str = Field(description="Query family label (e.g. proof, contrarian)")
    intent_tags: list[str] = Field(default_factory=list)
    query: str = Field(description="The actual search query string")
    mode: RetrievalMode = Field(default=RetrievalMode.BASELINE)
    rationale: str = Field(default="", description="Why this query was chosen")
    priority: int = Field(default=0, description="Higher = more important, runs first")


class RetrievalBudget(BaseModel):
    """Budget allocation for retrieval."""

    target_claims: int = 3
    max_sources_per_claim: int = 5
    min_authority: SourceAuthority = SourceAuthority.MEDIUM


class RetrievalPlan(BaseModel):
    """Retrieval plan for targeted research."""

    claim_id: str = ""
    claim: str = ""
    budget: RetrievalBudget = Field(default_factory=RetrievalBudget)
    expanded_queries: list[str] = Field(default_factory=list)
    decisions: list[RetrievalDecision] = Field(default_factory=list)
    mode: RetrievalMode = Field(default=RetrievalMode.BASELINE)
    research_depth_routing: "ResearchDepthRouting | None" = Field(default=None)
    research_hypotheses: list[str] = Field(default_factory=list)
    coverage_notes: list[str] = Field(default_factory=list)
    is_complete: bool = Field(default=False)

    @property
    def total_queries(self) -> int:
        return len(self.decisions)

    @property
    def families_used(self) -> set[str]:
        return {d.family for d in self.decisions}


def _dedupe_research_sources(sources: list[ResearchSource]) -> list[ResearchSource]:
    """Deduplicate sources by URL, keeping highest-ranked."""
    seen: dict[str, ResearchSource] = {}
    for src in sources:
        if src.url and src.url not in seen:
            seen[src.url] = src
        elif src.url and src.quality_rank > seen[src.url].quality_rank:
            seen[src.url] = src
    return list(seen.values())


def _ensure_unique_ids(
    items: list[BaseModel],
    *,
    id_attr: str,
    label: str,
) -> set[str]:
    """Ensure items have unique IDs and return the set of IDs."""
    ids: set[str] = set()
    for item in items:
        item_id = getattr(item, id_attr, None)
        if item_id and item_id in ids:
            raise ValueError(f"Duplicate {label} ID: {item_id}")
        if item_id:
            ids.add(item_id)
    return ids


def _ensure_known_ids(
    referenced_ids: list[str],
    *,
    valid_ids: set[str],
    label: str,
) -> None:
    """Ensure all referenced IDs are valid."""
    unknown = set(referenced_ids) - valid_ids
    if unknown:
        raise ValueError(f"Unknown {label} IDs: {sorted(unknown)}")
