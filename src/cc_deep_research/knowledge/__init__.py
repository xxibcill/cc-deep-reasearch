"""Knowledge vault domain models and type definitions."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Node and edge kinds
# ---------------------------------------------------------------------------


class NodeKind(StrEnum):
    """Kinds of nodes in the knowledge graph."""

    SESSION = "session"
    SOURCE = "source"
    QUERY = "query"
    CONCEPT = "concept"
    ENTITY = "entity"
    CLAIM = "claim"
    FINDING = "finding"
    GAP = "gap"
    QUESTION = "question"
    WIKI_PAGE = "wiki_page"


class EdgeKind(StrEnum):
    """Kinds of edges in the knowledge graph."""

    CITED = "cited"
    MENTIONS = "mentions"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DERIVED_FROM = "derived_from"
    USED_QUERY = "used_query"
    SUGGESTS_QUERY = "suggests_query"
    SUPERSEDES = "supersedes"
    EVOLVES = "evolves"
    LINKS_TO = "links_to"


# ---------------------------------------------------------------------------
# Page frontmatter
# ---------------------------------------------------------------------------


class PageStatus(StrEnum):
    """Status of a wiki page in the vault."""

    DRAFT = "draft"
    STABLE = "stable"
    DEPRECATED = "deprecated"
    NEEDS_REVIEW = "needs_review"


class PageFrontmatter(BaseModel):
    """Frontmatter fields for a wiki page in the knowledge vault."""

    id: str = Field(..., min_length=1)
    kind: NodeKind = Field(...)
    title: str = Field(..., min_length=1)
    status: PageStatus = Field(default=PageStatus.DRAFT)
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    session_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    # Allow extra metadata to pass through unchanged
    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# Graph models
# ---------------------------------------------------------------------------


class KnowledgeNode(BaseModel):
    """A node in the knowledge graph."""

    id: str = Field(..., min_length=1)
    kind: NodeKind = Field(...)
    label: str = Field(default="")
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"extra": "allow"}


class KnowledgeEdge(BaseModel):
    """A directed edge in the knowledge graph."""

    id: str = Field(..., min_length=1)
    source_id: str = Field(...)
    target_id: str = Field(...)
    kind: EdgeKind = Field(...)
    properties: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class GraphSnapshot(BaseModel):
    """A point-in-time snapshot of the knowledge graph."""

    nodes: list[KnowledgeNode] = Field(default_factory=list)
    edges: list[KnowledgeEdge] = Field(default_factory=list)
    exported_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Lint findings
# ------------------------------------------------------------------------


class LintSeverity(StrEnum):
    """Severity of a lint finding."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class LintFinding(BaseModel):
    """A single lint issue detected in the knowledge vault."""

    severity: LintSeverity = Field(...)
    category: str = Field(...)
    message: str = Field(...)
    node_id: str | None = Field(default=None)
    page_path: str | None = Field(default=None)
    source_id: str | None = Field(default=None)
    evidence: str | None = Field(default=None)


# ---------------------------------------------------------------------------
# Exports
# ------------------------------------------------------------------------

__all__ = [
    "EdgeKind",
    "GraphSnapshot",
    "KnowledgeEdge",
    "KnowledgeNode",
    "LintFinding",
    "LintSeverity",
    "NodeKind",
    "PageFrontmatter",
    "PageStatus",
]
