"""Reusable content asset models for extracting and repurposing content patterns."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ReusableAssetType(StrEnum):
    """Types of reusable content assets."""

    HOOK_PATTERN = "hook_pattern"  # A hook structure or template
    ANGLE_BEAT = "angle_beat"  # A reusable narrative beat or angle structure
    EVIDENCE_CITATION = "evidence_citation"  # A sourced proof anchor
    ARGUMENT_STRUCTURE = "argument_structure"  # An argument framework
    COUNTERARGUMENT = "counterargument"  # A counterargument + response pair
    PACKAGING_TEMPLATE = "packaging_template"  # A caption, hashtag, or CTA pattern
    VISUAL_BEAT = "visual_beat"  # A visual shot pattern or B-roll description
    FULL_BRIEF = "full_brief"  # A complete brief pattern


class ReusableAsset(BaseModel):
    """A reusable content asset extracted from a completed content-gen run.

    Assets carry provenance so operators can trace back to the original
    source and understand when/where they should be applied.
    """

    asset_id: str = Field(default_factory=lambda: f"ra_{uuid4().hex[:8]}")
    asset_type: ReusableAssetType = ReusableAssetType.HOOK_PATTERN

    # Human-readable labels
    name: str = ""
    description: str = ""

    # The actual reusable content
    content: str = ""  # The extracted text/pattern
    content_yaml: str = ""  # Structured content (beat plan, argument map excerpt, etc.)

    # Provenance - where this came from
    source_idea_id: str = ""
    source_run_id: str = ""
    source_brief_id: str = ""
    source_stage: str = ""  # e.g., "scripting", "packaging", "human_qc"
    extraction_reason: str = ""  # Why this was promoted (e.g., "high hook strength", "winning angle")

    # Metadata for search and filtering
    pillar: str = ""  # Content pillar / topic area
    audience: str = ""  # Target audience segment
    platform: str = ""  # Platform this was used on / for
    format: str = ""  # Content format (short_form, newsletter, etc.)

    # Performance context (optional, for sorting/filtering)
    performance_score: float = 0.0
    engagement_rate: float = 0.0
    view_count: int = 0

    # Usage tracking
    reuse_count: int = 0
    last_used_at: str = ""
    last_used_in_idea_id: str = ""

    # Timestamps
    created_at: str = ""
    updated_at: str = ""

    # Additional context
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_popular(self) -> bool:
        """Return True if this asset has been reused multiple times."""
        return self.reuse_count >= 3

    @property
    def is_proven(self) -> bool:
        """Return True if this asset has performance data showing positive results."""
        return self.engagement_rate > 0.05 or self.view_count > 1000


class AssetProvenanceLink(BaseModel):
    """A trace link from a reusable asset back to its origin content-gen run."""

    asset_id: str = ""
    source_idea_id: str = ""
    source_run_id: str = ""
    source_brief_id: str = ""
    source_stage: str = ""
    extraction_context: str = ""  # Why this was extracted at the time
    created_at: str = ""
