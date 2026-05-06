"""Entity and Source Deduplication Service for the knowledge vault.

Provides duplicate detection, candidate management, and merge operations
for knowledge graph nodes.
"""

from __future__ import annotations

import json
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from cc_deep_research.knowledge import (
    EdgeKind,
    KnowledgeEdge,
    KnowledgeNode,
    NodeKind,
)
from cc_deep_research.knowledge.graph_index import GraphIndex
from cc_deep_research.knowledge.vault import graph_dir

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class DuplicateMatchReason(StrEnum):
    """Reason why two nodes are considered duplicates."""

    SAME_URL = "same_url"
    SIMILAR_TITLE = "similar_title"
    SAME_ENTITY_LABEL = "same_entity_label"
    SIMILAR_TEXT = "similar_text"
    SHARED_SESSION = "shared_session"


class CandidateStatus(StrEnum):
    """Status of a duplicate candidate."""

    PENDING = "pending"
    MERGED = "merged"
    DISMISSED = "dismissed"
    DEFERRED = "deferred"


@dataclass
class DuplicateCandidate:
    """A candidate pair of potentially duplicate nodes."""

    id: str
    node_a_id: str
    node_b_id: str
    match_reason: DuplicateMatchReason
    confidence: float
    match_evidence: dict
    suggested_action: str
    created_at: datetime
    status: CandidateStatus = CandidateStatus.PENDING

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "node_a_id": self.node_a_id,
            "node_b_id": self.node_b_id,
            "match_reason": self.match_reason.value,
            "confidence": self.confidence,
            "match_evidence": self.match_evidence,
            "suggested_action": self.suggested_action,
            "created_at": self.created_at.isoformat(),
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> DuplicateCandidate:
        status_val = data.get("status", CandidateStatus.PENDING.value)
        try:
            status = CandidateStatus(status_val)
        except ValueError:
            status = CandidateStatus.PENDING
        return cls(
            id=data["id"],
            node_a_id=data["node_a_id"],
            node_b_id=data["node_b_id"],
            match_reason=DuplicateMatchReason(data["match_reason"]),
            confidence=data["confidence"],
            match_evidence=data.get("match_evidence", {}),
            suggested_action=data.get("suggested_action", "review"),
            created_at=datetime.fromisoformat(data["created_at"]),
            status=status,
        )


# ---------------------------------------------------------------------------
# Text normalization helpers
# ---------------------------------------------------------------------------


def _normalize_title(text: str) -> str:
    """Normalize a title for comparison.

    Lowercase, strip punctuation, collapse whitespace.
    """
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _normalize_claim_text(text: str) -> str:
    """Normalize claim text for similarity comparison.

    Lowercase, strip extra whitespace, normalize unicode.
    """
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    # Remove common filler words that don't add meaning
    filler = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being"}
    words = text.split()
    words = [w for w in words if w not in filler]
    return " ".join(words)


def _url_stem(url: str) -> str:
    """Derive a normalized stem from a URL for comparison.

    For 'https://example.com/page' returns 'page'
    For 'https://example.com' returns 'example.com'
    """
    # Remove protocol, query params, fragments
    parsed = url.split("?")[0].split("#")[0].rstrip("/")
    if "/" in parsed:
        # Has a path - get last segment
        segments = parsed.split("/")
        # Filter out empty segments from trailing slash
        segments = [s for s in segments if s]
        stem = segments[-1] if segments else parsed
    else:
        stem = parsed
    if not stem or stem in ("http:", "https:"):
        # Bare domain like https://example.com
        stem = parsed.split("/")[-1] if "/" in parsed else parsed
    return stem.lower()


def _ngrams(text: str, n: int = 3) -> set[str]:
    """Return character n-grams from text."""
    text = text.replace(" ", "_")
    if len(text) < n:
        return {text}
    return {text[i : i + n] for i in range(len(text) - n + 1)}


def _ngram_similarity(text1: str, text2: str, n: int = 3) -> float:
    """Compute n-gram overlap similarity between two texts.

    Returns a score from 0.0 to 1.0 based on Jaccard similarity of n-grams.
    """
    if not text1 or not text2:
        return 0.0
    grams1 = _ngrams(text1, n)
    grams2 = _ngrams(text2, n)
    intersection = len(grams1 & grams2)
    union = len(grams1 | grams2)
    if union == 0:
        return 0.0
    return intersection / union


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        s1, s2 = s2, s1
    if len(s2) == 0:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def _levenshtein_similarity(s1: str, s2: str) -> float:
    """Compute normalized similarity (0-1) based on Levenshtein distance."""
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    max_len = max(len(s1), len(s2))
    distance = _levenshtein_distance(s1, s2)
    return 1.0 - (distance / max_len)


def _combined_text_similarity(text1: str, text2: str) -> float:
    """Compute combined text similarity using both n-gram and Levenshtein.

    Returns the higher of the two scores.
    """
    ngram_score = _ngram_similarity(text1, text2)
    lev_score = _levenshtein_similarity(text1, text2)
    return max(ngram_score, lev_score)


# ---------------------------------------------------------------------------
# DuplicateCandidateStore
# ---------------------------------------------------------------------------


class DuplicateCandidateStore:
    """Persists duplicate candidate state in a JSON file."""

    def __init__(self, candidates_path: Path | None = None) -> None:
        if candidates_path is None:
            candidates_path = graph_dir() / "dedup_candidates.json"
        self._path = candidates_path
        self._candidates: list[DuplicateCandidate] = []
        self._merged_pairs: list[dict] = []
        self._load()

    def _load(self) -> None:
        """Load candidates and merged pairs from the JSON file."""
        if not self._path.exists():
            self._candidates = []
            self._merged_pairs = []
            return

        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._candidates = [
                DuplicateCandidate.from_dict(c) for c in data.get("candidates", [])
            ]
            self._merged_pairs = data.get("merged_pairs", [])
        except (json.JSONDecodeError, KeyError):
            self._candidates = []
            self._merged_pairs = []

    def _save(self) -> None:
        """Persist candidates and merged pairs to the JSON file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "candidates": [c.to_dict() for c in self._candidates],
            "merged_pairs": self._merged_pairs,
        }
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_candidates(self, status: CandidateStatus | None = None) -> list[DuplicateCandidate]:
        """Get all candidates, optionally filtered by status."""
        if status is None:
            return list(self._candidates)
        return [c for c in self._candidates if c.status == status]

    def get_pending_candidates(self) -> list[DuplicateCandidate]:
        """Get all pending candidates."""
        return [c for c in self._candidates if c.status == CandidateStatus.PENDING]

    def add_candidate(self, candidate: DuplicateCandidate) -> None:
        """Add a new candidate if it doesn't already exist."""
        existing_ids = {c.id for c in self._candidates}
        # Also check if same node pair already has a pending candidate
        existing_pairs = {
            (c.node_a_id, c.node_b_id) for c in self.get_pending_candidates()
        }
        pair = (candidate.node_a_id, candidate.node_b_id)
        if candidate.id in existing_ids or pair in existing_pairs:
            return
        self._candidates.append(candidate)
        self._save()

    def resolve_candidate(self, candidate_id: str, action: str) -> bool:
        """Mark a candidate as merged/dismissed/deferred.

        Returns True if the candidate was found and resolved.
        """
        for candidate in self._candidates:
            if candidate.id == candidate_id:
                try:
                    candidate.status = CandidateStatus(action.lower())
                except ValueError:
                    candidate.status = CandidateStatus.PENDING
                self._save()
                return True
        return False

    def add_merged_pair(
        self,
        node_a_id: str,
        node_b_id: str,
        kept_node_id: str,
        removed_node_id: str,
        session_ids: list[str],
        source_ids: list[str],
    ) -> None:
        """Record a merge operation for provenance tracking."""
        self._merged_pairs.append({
            "node_a_id": node_a_id,
            "node_b_id": node_b_id,
            "kept_node_id": kept_node_id,
            "removed_node_id": removed_node_id,
            "session_ids": session_ids,
            "source_ids": source_ids,
            "merged_at": datetime.now(UTC).isoformat(),
        })
        self._save()

    def get_merged_pairs(self) -> list[dict]:
        """Return pairs that were merged (for tracking provenance)."""
        return list(self._merged_pairs)

    def candidate(self, candidate_id: str) -> DuplicateCandidate | None:
        """Get a specific candidate by ID."""
        for c in self._candidates:
            if c.id == candidate_id:
                return c
        return None


# ---------------------------------------------------------------------------
# Core deduplication logic
# ---------------------------------------------------------------------------


def _build_label_normalized_index(nodes: list[KnowledgeNode]) -> dict[str, list[KnowledgeNode]]:
    """Build an index of nodes by normalized label."""
    index: dict[str, list[KnowledgeNode]] = defaultdict(list)
    for node in nodes:
        if node.label:
            norm = _normalize_title(node.label)
            index[norm].append(node)
    return index


def _build_url_index(nodes: list[KnowledgeNode]) -> dict[str, list[KnowledgeNode]]:
    """Build an index of source nodes by normalized URL stem."""
    index: dict[str, list[KnowledgeNode]] = defaultdict(list)
    for node in nodes:
        if node.kind == NodeKind.SOURCE:
            url = node.properties.get("url", "")
            if url:
                stem = _url_stem(url)
                index[stem].append(node)
    return index


def _is_session_node(node: KnowledgeNode) -> bool:
    """Return True if node is a session node."""
    return node.kind == NodeKind.SESSION


def _compute_suggested_action(reason: DuplicateMatchReason, confidence: float) -> str:
    """Determine suggested action based on match reason and confidence."""
    if confidence >= 0.9:
        return "merge"
    elif confidence >= 0.7:
        return "review"
    else:
        return "keep_separate"


def find_duplicate_candidates(index: GraphIndex) -> list[DuplicateCandidate]:
    """Find duplicate candidates in the graph index.

    Scans for:
    - URL duplicates: sources with same URL stem
    - Title duplicates: nodes with same normalized title (excluding sessions)
    - Entity duplicates: nodes with same label and kind (except sessions)
    - Claim text duplicates: claims with similar normalized text
    """
    candidates: list[DuplicateCandidate] = []
    all_nodes = index.all_nodes()

    if not all_nodes:
        return candidates

    seen_pairs: set[tuple[str, ...]] = set()

    def add_candidate(
        node_a: KnowledgeNode,
        node_b: KnowledgeNode,
        reason: DuplicateMatchReason,
        confidence: float,
        evidence: dict,
    ) -> None:
        """Add a candidate, avoiding duplicates and skipping session pairs."""
        if _is_session_node(node_a) and _is_session_node(node_b):
            return
        pair = tuple(sorted([node_a.id, node_b.id]))
        if pair in seen_pairs:
            return
        seen_pairs.add(pair)

        action = _compute_suggested_action(reason, confidence)
        candidate = DuplicateCandidate(
            id=str(uuid.uuid4()),
            node_a_id=node_a.id,
            node_b_id=node_b.id,
            match_reason=reason,
            confidence=confidence,
            match_evidence=evidence,
            suggested_action=action,
            created_at=datetime.now(UTC),
        )
        candidates.append(candidate)

    # 1. URL duplicates (source nodes with same URL stem)
    url_index = _build_url_index(all_nodes)
    for stem, nodes in url_index.items():
        if len(nodes) < 2:
            continue
        # Group by exact URL to find true duplicates
        url_groups: dict[str, list[KnowledgeNode]] = defaultdict(list)
        for node in nodes:
            url = node.properties.get("url", "")
            url_groups[url].append(node)

        for url, group in url_groups.items():
            if len(group) < 2:
                continue
            node_a, node_b = group[0], group[1]
            add_candidate(
                node_a,
                node_b,
                DuplicateMatchReason.SAME_URL,
                confidence=0.95,
                evidence={"url": url, "url_stem": stem},
            )

    # 2. Title duplicates: nodes with same normalized title
    label_index = _build_label_normalized_index(all_nodes)
    for norm_label, nodes in label_index.items():
        if len(nodes) < 2:
            continue
        # Skip if all nodes are sessions
        if all(_is_session_node(n) for n in nodes):
            continue

        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                node_a, node_b = nodes[i], nodes[j]
                if _is_session_node(node_a) and _is_session_node(node_b):
                    continue

                if node_a.kind == node_b.kind:
                    # Same kind and similar title
                    add_candidate(
                        node_a,
                        node_b,
                        DuplicateMatchReason.SIMILAR_TITLE,
                        confidence=0.75,
                        evidence={
                            "title_a": node_a.label,
                            "title_b": node_b.label,
                            "normalized": norm_label,
                        },
                    )
                else:
                    # Different kinds, same label - lower confidence
                    add_candidate(
                        node_a,
                        node_b,
                        DuplicateMatchReason.SAME_ENTITY_LABEL,
                        confidence=0.6,
                        evidence={
                            "label": norm_label,
                            "kind_a": node_a.kind.value,
                            "kind_b": node_b.kind.value,
                        },
                    )

    # 3. Entity duplicates: nodes with same label and kind (except sessions)
    kind_label_index: dict[tuple[str, str], list[KnowledgeNode]] = defaultdict(list)
    for node in all_nodes:
        if node.label and not _is_session_node(node):
            key = (node.kind.value, _normalize_title(node.label))
            kind_label_index[key].append(node)

    for (kind, label), nodes in kind_label_index.items():
        if len(nodes) < 2:
            continue
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                node_a, node_b = nodes[i], nodes[j]
                add_candidate(
                    node_a,
                    node_b,
                    DuplicateMatchReason.SAME_ENTITY_LABEL,
                    confidence=0.85,
                    evidence={
                        "label": label,
                        "kind": kind,
                    },
                )

    # 4. Claim text duplicates: claims with similar normalized text
    claim_nodes = [n for n in all_nodes if n.kind == NodeKind.CLAIM and n.label]
    for i in range(len(claim_nodes)):
        for j in range(i + 1, len(claim_nodes)):
            claim_a = claim_nodes[i]
            claim_b = claim_nodes[j]

            norm_a = _normalize_claim_text(claim_a.label)
            norm_b = _normalize_claim_text(claim_b.label)

            if not norm_a or not norm_b:
                continue

            similarity = _combined_text_similarity(norm_a, norm_b)
            if similarity >= 0.7:
                add_candidate(
                    claim_a,
                    claim_b,
                    DuplicateMatchReason.SIMILAR_TEXT,
                    confidence=similarity,
                    evidence={
                        "text_a": claim_a.label[:200],
                        "text_b": claim_b.label[:200],
                        "normalized_a": norm_a[:200],
                        "normalized_b": norm_b[:200],
                        "similarity_score": round(similarity, 3),
                    },
                )

    # 5. Shared session duplicates: nodes from the same session
    # Build session_id -> nodes mapping
    session_nodes: dict[str, list[KnowledgeNode]] = defaultdict(list)
    for node in all_nodes:
        sid = node.properties.get("session_id") or node.properties.get("session_ids", [])
        if isinstance(sid, list):
            for s in sid:
                session_nodes[s].append(node)
        else:
            session_nodes[sid].append(node)

    for session_id, nodes in session_nodes.items():
        if len(nodes) < 2:
            continue
        # Find duplicate candidates within this session
        label_group: dict[str, list[KnowledgeNode]] = defaultdict(list)
        for node in nodes:
            if node.label:
                label_group[_normalize_title(node.label)].append(node)

        for norm_label, grouped in label_group.items():
            if len(grouped) < 2:
                continue
            # Only flag as shared session if not already caught by other reasons
            for i in range(len(grouped)):
                for j in range(i + 1, len(grouped)):
                    node_a, node_b = grouped[i], grouped[j]
                    pair = tuple(sorted([node_a.id, node_b.id]))
                    # Skip if already have a candidate for this pair
                    if pair in seen_pairs:
                        continue
                    add_candidate(
                        node_a,
                        node_b,
                        DuplicateMatchReason.SHARED_SESSION,
                        confidence=0.5,
                        evidence={
                            "session_id": session_id,
                            "label": norm_label,
                        },
                    )

    return candidates


# ---------------------------------------------------------------------------
# Merge operations
# ---------------------------------------------------------------------------


def merge_nodes(
    index: GraphIndex,
    node_a_id: str,
    node_b_id: str,
    *,
    store: DuplicateCandidateStore | None = None,
) -> dict:
    """Merge two nodes, preserving provenance.

    The kept node retains all session_ids and source_ids from both nodes.
    A SUPERSEDES edge is created from kept to removed node.
    Returns a dict with merge details.
    """
    node_a = index.node(node_a_id)
    node_b = index.node(node_b_id)

    if node_a is None or node_b is None:
        return {"success": False, "error": "One or both nodes not found"}

    # Determine which node to keep (keep the one with more connections, or just node_a)
    all_edges = index.all_edges()
    a_edges = [e for e in all_edges if e.source_id == node_a_id or e.target_id == node_a_id]
    b_edges = [e for e in all_edges if e.source_id == node_b_id or e.target_id == node_b_id]

    if len(b_edges) > len(a_edges):
        kept_node = node_b
        removed_node = node_a
        kept_id, removed_id = node_b_id, node_a_id
    else:
        kept_node = node_a
        removed_node = node_b
        kept_id, removed_id = node_a_id, node_b_id

    # Get the actual removed node object
    removed_node_obj = index.node(removed_id)

    # Merge properties
    merged_properties = dict(kept_node.properties)
    if removed_node_obj is not None:
        for key, value in removed_node_obj.properties.items():
            if key not in merged_properties:
                merged_properties[key] = value
            elif key == "session_ids" and isinstance(value, list):
                existing = merged_properties.get("session_ids", [])
                if isinstance(existing, list):
                    combined = list(set(existing + value))
                    merged_properties["session_ids"] = combined
            elif key == "source_ids" and isinstance(value, list):
                existing = merged_properties.get("source_ids", [])
                if isinstance(existing, list):
                    combined = list(set(existing + value))
                    merged_properties["source_ids"] = combined

    # Update kept node
    kept_node.properties = merged_properties
    index.upsert_node(kept_node)

    # Create SUPERSEDES edge
    edge_id = f"supersedes:{kept_id}:{removed_id}"
    supersedes_edge = KnowledgeEdge(
        id=edge_id,
        source_id=kept_id,
        target_id=removed_id,
        kind=EdgeKind.SUPERSEDES,
        properties={
            "merged_at": datetime.now(UTC).isoformat(),
            "removed_node_id": removed_id,
        },
    )
    index.upsert_edge(supersedes_edge)

    # Re-target edges from removed node to kept node
    for edge in all_edges:
        if edge.source_id == removed_id:
            new_edge = KnowledgeEdge(
                id=f"{edge.kind.value}:{kept_id}:{edge.target_id}",
                source_id=kept_id,
                target_id=edge.target_id,
                kind=edge.kind,
                properties=dict(edge.properties),
            )
            index.upsert_edge(new_edge)
        if edge.target_id == removed_id:
            new_edge = KnowledgeEdge(
                id=f"{edge.kind.value}:{edge.source_id}:{kept_id}",
                source_id=edge.source_id,
                target_id=kept_id,
                kind=edge.kind,
                properties=dict(edge.properties),
            )
            index.upsert_edge(new_edge)

    # Collect session_ids and source_ids for provenance
    session_ids = list(set(
        merged_properties.get("session_ids", [])
        if isinstance(merged_properties.get("session_ids"), list)
        else []
    ))
    source_ids = list(set(
        merged_properties.get("source_ids", [])
        if isinstance(merged_properties.get("source_ids"), list)
        else []
    ))

    # Record in store
    if store is not None:
        store.add_merged_pair(
            node_a_id=node_a_id,
            node_b_id=node_b_id,
            kept_node_id=kept_id,
            removed_node_id=removed_id,
            session_ids=session_ids,
            source_ids=source_ids,
        )

    index.commit()

    return {
        "success": True,
        "kept_node_id": kept_id,
        "removed_node_id": removed_id,
        "session_ids": session_ids,
        "source_ids": source_ids,
        "supersedes_edge_id": edge_id,
    }


__all__ = [
    "CandidateStatus",
    "DuplicateCandidate",
    "DuplicateCandidateStore",
    "DuplicateMatchReason",
    "find_duplicate_candidates",
    "merge_nodes",
]
