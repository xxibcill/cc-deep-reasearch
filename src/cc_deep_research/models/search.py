"""Search-domain models and helpers."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ResearchDepth(StrEnum):
    """Research depth modes."""

    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class SearchOptions(BaseModel):
    """Options for search operations."""

    max_results: int = Field(default=10, ge=1, le=100)
    include_raw_content: bool = Field(default=True)
    search_depth: ResearchDepth = Field(default=ResearchDepth.DEEP)
    monitor: bool = Field(default=False)


class QueryProvenance(BaseModel):
    """Trace one source back to the query variation that produced it."""

    query: str = Field(..., min_length=1)
    family: str = Field(default="baseline")
    intent_tags: list[str] = Field(default_factory=list)


def _dedupe_strings(values: list[str]) -> list[str]:
    """Return unique strings in first-seen order."""
    return list(dict.fromkeys(value for value in values if value))


def _normalize_query_provenance_entries(value: Any) -> list[QueryProvenance]:
    """Coerce mixed provenance payloads into typed entries."""
    if isinstance(value, QueryProvenance):
        candidates: list[Any] = [value]
    elif isinstance(value, Mapping):
        candidates = [value]
    elif isinstance(value, list):
        candidates = value
    else:
        return []

    normalized: list[QueryProvenance] = []
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    for candidate in candidates:
        try:
            entry = (
                candidate
                if isinstance(candidate, QueryProvenance)
                else QueryProvenance.model_validate(candidate)
            )
        except Exception:
            continue
        entry.intent_tags = _dedupe_strings([str(tag) for tag in entry.intent_tags])
        key = (entry.query, entry.family, tuple(entry.intent_tags))
        if key in seen:
            continue
        seen.add(key)
        normalized.append(entry)
    return normalized


class SearchResultItem(BaseModel):
    """A single search result item."""

    url: str = Field(..., min_length=1)
    title: str = Field(default="")
    snippet: str = Field(default="")
    content: str | None = Field(default=None)
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    query_provenance: list[QueryProvenance] = Field(default_factory=list)

    model_config = {"frozen": False}

    @model_validator(mode="after")
    def _normalize_provenance(self) -> SearchResultItem:
        """Keep provenance fields synchronized with source metadata."""
        metadata = dict(self.source_metadata)
        provenance = _normalize_query_provenance_entries(self.query_provenance)

        if not provenance:
            provenance = _normalize_query_provenance_entries(metadata.get("query_provenance"))

        if not provenance and metadata.get("query"):
            provenance = _normalize_query_provenance_entries(
                {
                    "query": metadata.get("query"),
                    "family": metadata.get("query_family", "baseline"),
                    "intent_tags": metadata.get("query_intent_tags", []),
                }
            )

        self.query_provenance = provenance
        if not provenance:
            return self

        metadata["query_provenance"] = [
            entry.model_dump(mode="python") for entry in provenance
        ]
        metadata["queries"] = _dedupe_strings([entry.query for entry in provenance])
        metadata["query_families"] = _dedupe_strings([entry.family for entry in provenance])
        if len(provenance) == 1:
            metadata["query"] = provenance[0].query
            metadata["query_family"] = provenance[0].family
            metadata["query_intent_tags"] = list(provenance[0].intent_tags)
        else:
            metadata.pop("query", None)
            metadata.pop("query_family", None)
            metadata.pop("query_intent_tags", None)
        self.source_metadata = metadata
        return self

    def add_query_provenance(
        self,
        *,
        query: str,
        family: str = "baseline",
        intent_tags: list[str] | None = None,
    ) -> None:
        """Attach one query provenance entry to the source."""
        merged = _normalize_query_provenance_entries(
            [
                *self.query_provenance,
                {
                    "query": query,
                    "family": family,
                    "intent_tags": intent_tags or [],
                },
            ]
        )
        self.query_provenance = merged
        self._normalize_provenance()  # type: ignore[operator]


class SearchResult(BaseModel):
    """Result from a search operation."""

    query: str = Field(..., min_length=1)
    results: list[SearchResultItem] = Field(default_factory=list)
    provider: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    execution_time_ms: int = Field(default=0, ge=0)


class QueryProfile(BaseModel):
    """Lightweight profile derived from the incoming research query."""

    intent: str = Field(default="informational")
    is_time_sensitive: bool = Field(default=False)
    key_terms: list[str] = Field(default_factory=list)
    target_source_classes: list[str] = Field(default_factory=list)


class QueryFamily(BaseModel):
    """A labeled query expansion with explicit retrieval purpose."""

    query: str = Field(..., min_length=1)
    family: str = Field(default="baseline")
    intent_tags: list[str] = Field(default_factory=list)


__all__ = [
    "QueryFamily",
    "QueryProfile",
    "QueryProvenance",
    "ResearchDepth",
    "SearchOptions",
    "SearchResult",
    "SearchResultItem",
]
