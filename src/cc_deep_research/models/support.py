"""Shared non-domain-specific models and evidence contracts."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from .search import QueryProvenance, SearchResultItem, _normalize_query_provenance_entries


class SearchMode(StrEnum):
    """Search mode for orchestrator."""

    HYBRID_PARALLEL = "hybrid_parallel"
    TAVILY_PRIMARY = "tavily_primary"
    CLAUDE_PRIMARY = "claude_primary"


class QualityScore(BaseModel):
    """Quality score for a source."""

    credibility: float = Field(default=0.5, ge=0.0, le=1.0)
    relevance: float = Field(default=0.5, ge=0.0, le=1.0)
    freshness: float = Field(default=0.5, ge=0.0, le=1.0)
    diversity: float = Field(default=0.5, ge=0.0, le=1.0)
    overall: float = Field(default=0.5, ge=0.0, le=1.0)


class EvidenceType(StrEnum):
    """High-level classification for evidence attached to a claim."""

    PRIMARY = "primary"
    RESEARCH = "research"
    NEWS = "news"
    OFFICIAL = "official"
    SECONDARY = "secondary"
    UNKNOWN = "unknown"


class ClaimFreshness(StrEnum):
    """Freshness bucket for evidence or claims."""

    CURRENT = "current"
    RECENT = "recent"
    DATED = "dated"
    UNKNOWN = "unknown"


class SourceType(StrEnum):
    """Enhanced source classification for quality assessment."""

    PRIMARY_RESEARCH = "primary_research"
    PREPRINT = "preprint"
    META_ANALYSIS = "meta_analysis"
    SYSTEMATIC_REVIEW = "systematic_review"
    MEDICAL_REFERENCE = "medical_reference"
    COMMERCIAL_BLOG = "commercial_blog"
    OFFICIAL_DOCUMENT = "official_document"
    PROTOCOL_DOCUMENT = "protocol_document"
    GENERAL_WEB = "general_web"


class ResearchGapType(str):
    """Types of research gaps that can be automatically detected."""

    MISSING_QUANTITATIVE_DATA = "missing_quantitative_data"
    MISSING_COMPARATIVE_STUDIES = "missing_comparative_studies"
    MISSING_MECHANISM_DETAILS = "missing_mechanism_details"
    MISSING_SAFETY_DATA = "missing_safety_data"
    MISSING_CLINICAL_TRIALS = "missing_clinical_trials"
    MISSING_LONGITUDINAL_DATA = "missing_longitudinal_data"


def _parse_published_date(value: Any) -> datetime | None:
    """Parse loose publication dates from source metadata."""
    if not value:
        return None

    text = str(value).strip()
    if not text:
        return None

    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
    return None


def _classify_claim_freshness(value: Any) -> ClaimFreshness:
    """Map a publication date into coarse freshness buckets."""
    published_at = _parse_published_date(value)
    if published_at is None:
        return ClaimFreshness.UNKNOWN

    age_days = max(0, (datetime.utcnow() - published_at).days)
    if age_days <= 30:
        return ClaimFreshness.CURRENT
    if age_days <= 365:
        return ClaimFreshness.RECENT
    return ClaimFreshness.DATED


def _infer_evidence_type(
    *,
    url: str,
    title: str,
    metadata: Mapping[str, Any],
    query_provenance: list[QueryProvenance],
) -> EvidenceType:
    """Infer an evidence class from stable source signals."""
    haystack = " ".join(
        [
            url.lower(),
            title.lower(),
            " ".join(str(tag).lower() for tag in metadata.get("query_intent_tags", [])),
            " ".join(entry.family.lower() for entry in query_provenance),
            " ".join(tag.lower() for entry in query_provenance for tag in entry.intent_tags),
        ]
    )

    if any(token in haystack for token in ("pubmed", "doi.org", "journal", "clinical trial")):
        return EvidenceType.RESEARCH
    if any(token in haystack for token in (".gov", ".edu", "sec.", "fda", "cdc", "who.int")):
        return EvidenceType.OFFICIAL
    if any(token in haystack for token in ("reuters", "apnews", "bloomberg", "nytimes", "news")):
        return EvidenceType.NEWS
    if any(token in haystack for token in ("primary-source", "evidence", "filing", "transcript")):
        return EvidenceType.PRIMARY
    if any(token in haystack for token in ("wikipedia", "blog", "review", "summary")):
        return EvidenceType.SECONDARY
    return EvidenceType.UNKNOWN


class ClaimEvidence(BaseModel):
    """One source item attached to a supporting or contradicting claim."""

    url: str = Field(..., min_length=1)
    title: str = Field(default="")
    snippet: str = Field(default="")
    published_date: str | None = Field(default=None)
    query_provenance: list[QueryProvenance] = Field(default_factory=list)
    freshness: ClaimFreshness = Field(default=ClaimFreshness.UNKNOWN)
    evidence_type: EvidenceType = Field(default=EvidenceType.UNKNOWN)
    source_metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_source_shapes(cls, value: Any) -> Any:
        """Accept URLs, source models, and raw dictionaries."""
        if isinstance(value, ClaimEvidence):
            return value
        if isinstance(value, str):
            return {"url": value}
        if isinstance(value, SearchResultItem):
            return {
                "url": value.url,
                "title": value.title,
                "snippet": value.snippet or value.content or "",
                "published_date": (
                    value.source_metadata.get("published_date")
                    or value.source_metadata.get("published")
                ),
                "query_provenance": [
                    entry.model_dump(mode="python") for entry in value.query_provenance
                ],
                "source_metadata": dict(value.source_metadata),
            }
        if isinstance(value, Mapping):
            payload = dict(value)
            if "source_url" in payload and "url" not in payload:
                payload["url"] = payload["source_url"]
            if "metadata" in payload and "source_metadata" not in payload:
                metadata = payload.get("metadata")
                payload["source_metadata"] = (
                    dict(metadata) if isinstance(metadata, Mapping) else {}
                )
            return payload
        return value

    @model_validator(mode="after")
    def _normalize_metadata(self) -> "ClaimEvidence":
        """Synchronize provenance, freshness, and evidence typing."""
        metadata = dict(self.source_metadata)
        provenance = _normalize_query_provenance_entries(self.query_provenance)
        if not provenance:
            provenance = _normalize_query_provenance_entries(metadata.get("query_provenance"))
        self.query_provenance = provenance

        if self.published_date is None:
            self.published_date = metadata.get("published_date") or metadata.get("published")
        if self.freshness == ClaimFreshness.UNKNOWN:
            self.freshness = _classify_claim_freshness(self.published_date)
        if self.evidence_type == EvidenceType.UNKNOWN:
            self.evidence_type = _infer_evidence_type(
                url=self.url,
                title=self.title,
                metadata=metadata,
                query_provenance=provenance,
            )

        metadata["query_provenance"] = [
            entry.model_dump(mode="python") for entry in self.query_provenance
        ]
        if self.published_date:
            metadata["published_date"] = self.published_date
        metadata["freshness"] = self.freshness.value
        metadata["evidence_type"] = self.evidence_type.value
        self.source_metadata = metadata
        return self


def _normalize_claim_evidence_entries(value: Any) -> list[ClaimEvidence]:
    """Coerce mixed evidence payloads into typed evidence entries."""
    if isinstance(value, list):
        raw_entries = value
    elif value is None:
        raw_entries = []
    else:
        raw_entries = [value]

    normalized: list[ClaimEvidence] = []
    seen: set[str] = set()
    for entry in raw_entries:
        try:
            evidence = ClaimEvidence.model_validate(entry)
        except Exception:
            continue
        if evidence.url in seen:
            continue
        seen.add(evidence.url)
        normalized.append(evidence)
    return normalized


def _derive_claim_freshness(evidence: list[ClaimEvidence]) -> ClaimFreshness:
    """Derive a claim freshness rating from attached evidence."""
    if not evidence:
        return ClaimFreshness.UNKNOWN
    if any(item.freshness == ClaimFreshness.CURRENT for item in evidence):
        return ClaimFreshness.CURRENT
    if any(item.freshness == ClaimFreshness.RECENT for item in evidence):
        return ClaimFreshness.RECENT
    if any(item.freshness == ClaimFreshness.DATED for item in evidence):
        return ClaimFreshness.DATED
    return ClaimFreshness.UNKNOWN


def _derive_claim_evidence_type(evidence: list[ClaimEvidence]) -> EvidenceType:
    """Select the dominant evidence type across supporting evidence."""
    types = [
        item.evidence_type
        for item in evidence
        if item.evidence_type != EvidenceType.UNKNOWN
    ]
    if not types:
        return EvidenceType.UNKNOWN
    return Counter(types).most_common(1)[0][0]


def _derive_claim_confidence(
    support_count: int,
    contradiction_count: int,
    consensus_level: float,
) -> str:
    """Infer a coarse confidence level from support and contradiction counts."""
    if support_count >= 3 and contradiction_count == 0 and consensus_level >= 0.6:
        return "high"
    if support_count >= 2 and contradiction_count <= 1:
        return "medium"
    return "low"


class CrossReferenceClaim(BaseModel):
    """A claim found across multiple sources."""

    claim: str
    supporting_sources: list[ClaimEvidence] = Field(default_factory=list)
    contradicting_sources: list[ClaimEvidence] = Field(default_factory=list)
    confidence: str | None = Field(default=None)
    freshness: ClaimFreshness | None = Field(default=None)
    evidence_type: EvidenceType | None = Field(default=None)
    consensus_level: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("supporting_sources", "contradicting_sources", mode="before")
    @classmethod
    def _normalize_sources(cls, value: Any) -> list[ClaimEvidence]:
        """Accept legacy URL lists and normalize them to claim evidence."""
        return _normalize_claim_evidence_entries(value)

    @model_validator(mode="after")
    def _derive_metadata(self) -> "CrossReferenceClaim":
        """Fill derived claim metadata from attached evidence."""
        if self.freshness is None:
            self.freshness = _derive_claim_freshness(self.supporting_sources)
        if self.evidence_type is None:
            self.evidence_type = _derive_claim_evidence_type(self.supporting_sources)
        if self.confidence is None:
            self.confidence = _derive_claim_confidence(
                support_count=len(self.supporting_sources),
                contradiction_count=len(self.contradicting_sources),
                consensus_level=self.consensus_level,
            )
        return self


class ReportEvaluationResult(BaseModel):
    """Typed result from report quality evaluation phase."""

    overall_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    is_acceptable: bool = Field(default=False)
    writing_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    structure_flow_score: float = Field(default=0.0, ge=0.0, le=1.0)
    technical_accuracy_score: float = Field(default=0.0, ge=0.0, le=1.0)
    user_experience_score: float = Field(default=0.0, ge=0.0, le=1.0)
    consistency_score: float = Field(default=0.0, ge=0.0, le=1.0)
    critical_issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    dimension_assessments: dict[str, Any] = Field(default_factory=dict)
    evaluation_method: str = Field(default="llm_analysis")


class APIKey(BaseModel):
    """Represents an API key with usage tracking."""

    key: str = Field(..., min_length=1)
    requests_used: int = Field(default=0, ge=0)
    requests_limit: int = Field(default=1000, ge=1)
    last_used: datetime | None = Field(default=None)
    disabled: bool = Field(default=False)

    @property
    def is_available(self) -> bool:
        """Check if this key is available for use."""
        return not self.disabled and self.requests_used < self.requests_limit

    @property
    def remaining_requests(self) -> int:
        """Get remaining requests for this key."""
        return max(0, self.requests_limit - self.requests_used)


__all__ = [
    "APIKey",
    "ClaimEvidence",
    "ClaimFreshness",
    "CrossReferenceClaim",
    "EvidenceType",
    "QualityScore",
    "ReportEvaluationResult",
    "ResearchGapType",
    "SearchMode",
    "SourceType",
]
