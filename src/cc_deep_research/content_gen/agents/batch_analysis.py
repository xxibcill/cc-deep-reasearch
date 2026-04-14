"""Batch analysis utilities for backlog triage.

Heuristic pre-processing to support the triage agent:
- Duplicate detection (exact and near-duplicate)
- Sparsity scoring for enrichment targeting
- Gap analysis across category, audience, evidence
"""

from __future__ import annotations

import re
from collections import defaultdict

from cc_deep_research.content_gen.models import BacklogItem


def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def jaccard_similarity(a: str, b: str) -> float:
    """Compute Jaccard similarity between two strings."""
    if not a or not b:
        return 0.0
    set_a = set(a.split())
    set_b = set(b.split())
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def token_overlap_ratio(a: str, b: str) -> float:
    """Compute token overlap ratio between two strings."""
    if not a or not b:
        return 0.0
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    smaller = tokens_a if len(tokens_a) <= len(tokens_b) else tokens_b
    larger = tokens_b if len(tokens_a) <= len(tokens_b) else tokens_a
    overlap = len(smaller & larger)
    return overlap / len(smaller)


def cosine_similarity_vec(a: str, b: str) -> float:
    """Simple cosine similarity using word frequency vectors."""
    if not a or not b:
        return 0.0
    words_a = a.split()
    words_b = b.split()
    if not words_a or not words_b:
        return 0.0
    vec_a = set(words_a)
    vec_b = set(words_b)
    dot = len(vec_a & vec_b)
    norm_a = len(vec_a) ** 0.5
    norm_b = len(vec_b) ** 0.5
    return dot / (norm_a * norm_b) if norm_a > 0 and norm_b > 0 else 0.0


class DuplicateCandidate:
    """A duplicate candidate pair with similarity score."""

    def __init__(
        self,
        idea_id_a: str,
        idea_id_b: str,
        score: float,
        reason: str,
        preferred_id: str | None = None,
    ) -> None:
        self.idea_id_a = idea_id_a
        self.idea_id_b = idea_id_b
        self.score = score
        self.reason = reason
        self.preferred_id = preferred_id


def find_exact_duplicates(items: list[BacklogItem]) -> list[DuplicateCandidate]:
    """Find items with identical normalized idea text."""
    by_normalized: dict[str, list[str]] = defaultdict(list)
    for item in items:
        if not item.idea:
            continue
        norm = normalize_text(item.idea)
        if norm:
            by_normalized[norm].append(item.idea_id)

    duplicates = []
    for norm, ids in by_normalized.items():
        if len(ids) > 1:
            # Keep the first one as preferred
            preferred = ids[0]
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    duplicates.append(
                        DuplicateCandidate(
                            idea_id_a=ids[i],
                            idea_id_b=ids[j],
                            score=1.0,
                            reason=f"Exact duplicate idea text: '{norm[:50]}'",
                            preferred_id=preferred,
                        )
                    )
    return duplicates


def find_near_duplicates(
    items: list[BacklogItem],
    *,
    min_similarity: float = 0.65,
    max_candidates: int = 50,
) -> list[DuplicateCandidate]:
    """Find items with near-duplicate idea text using Jaccard similarity."""
    ideas_with_ids = [(item.idea_id, normalize_text(item.idea)) for item in items if item.idea]
    candidates: list[tuple[str, str, float]] = []

    for i, (id_a, norm_a) in enumerate(ideas_with_ids):
        for j, (id_b, norm_b) in enumerate(ideas_with_ids):
            if i >= j:
                continue
            if not norm_a or not norm_b:
                continue
            sim = jaccard_similarity(norm_a, norm_b)
            if sim >= min_similarity:
                candidates.append((id_a, id_b, sim))

    # Sort by similarity descending
    candidates.sort(key=lambda x: x[2], reverse=True)

    duplicates = []
    seen_pairs: set[frozenset[str]] = set()
    for id_a, id_b, score in candidates:
        pair = frozenset([id_a, id_b])
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        # Determine preferred: keep one with more content or higher score
        item_a = next((x for x in items if x.idea_id == id_a), None)
        item_b = next((x for x in items if x.idea_id == id_b), None)
        preferred = id_a  # default
        if item_a and item_b:
            # Prefer item with more evidence/hooks
            a_content = sum(
                1 for f in ["evidence", "why_now", "potential_hook"] if getattr(item_a, f, "")
            )
            b_content = sum(
                1 for f in ["evidence", "why_now", "potential_hook"] if getattr(item_b, f, "")
            )
            if b_content > a_content:
                preferred = id_b

        duplicates.append(
            DuplicateCandidate(
                idea_id_a=id_a,
                idea_id_b=id_b,
                score=score,
                reason=f"Near-duplicate (Jaccard={score:.2f}): similar idea phrasing",
                preferred_id=preferred,
            )
        )

        if len(duplicates) >= max_candidates:
            break

    return duplicates


class SparsityScore:
    """Sparsity score for an item with detail."""

    def __init__(
        self,
        idea_id: str,
        score: float,
        missing_fields: list[str],
        weak_fields: list[str],
    ) -> None:
        self.idea_id = idea_id
        self.score = score
        self.missing_fields = missing_fields
        self.weak_fields = weak_fields


def score_sparsity(items: list[BacklogItem]) -> list[SparsityScore]:
    """Score items by sparsity (how much enrichment is needed).

    Lower score = more sparse/needs enrichment.
    Higher score = more complete/already well-developed.
    """
    # Fields that contribute to completeness
    CONTENT_FIELDS = [
        "idea",
        "audience",
        "problem",
        "evidence",
        "why_now",
        "potential_hook",
    ]
    ENRICHMENT_FIELDS = [
        "evidence",
        "why_now",
        "potential_hook",
        "genericity_risk",
        "proof_gap_note",
    ]

    results = []
    for item in items:
        missing: list[str] = []
        weak: list[str] = []
        score = 0.0

        for field in CONTENT_FIELDS:
            value = getattr(item, field, "") or ""
            if not value.strip():
                missing.append(field)
            elif len(value.strip()) < 20:
                weak.append(field)
            else:
                score += 1.0

        # Enrichment fields get weighted less (they're nice-to-have)
        for field in ENRICHMENT_FIELDS:
            value = getattr(item, field, "") or ""
            if value.strip():
                score += 0.5  # partial credit

        # Deduct for very short ideas
        if item.idea and len(item.idea) < 30:
            score -= 0.5

        # Boost for high priority items
        if item.priority_score and item.priority_score > 0.7:
            score += 0.5

        results.append(
            SparsityScore(
                idea_id=item.idea_id,
                score=score,
                missing_fields=missing,
                weak_fields=weak,
            )
        )

    # Sort by score ascending (most sparse first)
    results.sort(key=lambda x: x.score)
    return results


def find_sparse_items(
    items: list[BacklogItem],
    *,
    top_n: int = 10,
) -> list[SparsityScore]:
    """Find the most sparse items that would benefit from enrichment."""
    sparsity_scores = score_sparsity(items)
    return sparsity_scores[:top_n]


class GapAnalysis:
    """Gap analysis result for a category."""

    def __init__(
        self,
        gap_type: str,
        description: str,
        affected_idea_ids: list[str],
        suggestion: str,
    ) -> None:
        self.gap_type = gap_type
        self.description = description
        self.affected_idea_ids = affected_idea_ids
        self.suggestion = suggestion


def analyze_gaps(items: list[BacklogItem]) -> list[GapAnalysis]:
    """Analyze the backlog for gaps across category, audience, evidence, and freshness."""
    gaps: list[GapAnalysis] = []

    # Category gaps
    categories = [item.category for item in items if item.category]
    category_counts: dict[str, int] = defaultdict(int)
    for cat in categories:
        category_counts[cat] += 1

    if "trend-responsive" not in category_counts:
        gaps.append(
            GapAnalysis(
                gap_type="category",
                description="No trend-responsive items in backlog",
                affected_idea_ids=[],
                suggestion="Consider adding items that capitalize on current trends",
            )
        )

    if "evergreen" not in category_counts:
        gaps.append(
            GapAnalysis(
                gap_type="category",
                description="No evergreen content items",
                affected_idea_ids=[],
                suggestion="Add evergreen content that remains relevant over time",
            )
        )

    # Audience gaps
    audiences = [item.audience for item in items if item.audience]
    audience_set = set(audiences)
    if len(audience_set) < 2:
        gaps.append(
            GapAnalysis(
                gap_type="audience",
                description=f"Only {len(audience_set)} unique audience(s) defined",
                affected_idea_ids=[item.idea_id for item in items if item.audience],
                suggestion="Diversify across multiple audience segments",
            )
        )

    # Evidence gaps - items missing evidence
    items_without_evidence = [
        item.idea_id for item in items if item.evidence and len(item.evidence) < 10
    ]
    if items_without_evidence:
        gaps.append(
            GapAnalysis(
                gap_type="evidence",
                description=f"{len(items_without_evidence)} items lack strong evidence",
                affected_idea_ids=items_without_evidence[:5],  # limit to first 5
                suggestion="Add supporting evidence or proof points to these items",
            )
        )

    # Freshness gaps - items missing why_now
    items_without_why_now = [
        item.idea_id for item in items if not item.why_now or len(item.why_now) < 10
    ]
    if items_without_why_now:
        gaps.append(
            GapAnalysis(
                gap_type="freshness",
                description=f"{len(items_without_why_now)} items missing 'why now' context",
                affected_idea_ids=items_without_why_now[:5],
                suggestion="Add urgency or timeliness context to explain why these matter now",
            )
        )

    # Hook gaps
    items_without_hook = [
        item.idea_id for item in items if not item.potential_hook or len(item.potential_hook) < 10
    ]
    if items_without_hook:
        gaps.append(
            GapAnalysis(
                gap_type="hook",
                description=f"{len(items_without_hook)} items lack hooks",
                affected_idea_ids=items_without_hook[:5],
                suggestion="Develop strong hooks or opening angles for these items",
            )
        )

    return gaps


def cluster_by_theme(items: list[BacklogItem]) -> dict[str, list[BacklogItem]]:
    """Cluster items by source_theme or inferred theme."""
    clusters: dict[str, list[BacklogItem]] = defaultdict(list)

    for item in items:
        theme = item.source_theme or ""
        if not theme:
            # Try to infer from idea text
            theme = _infer_theme(item.idea)
        if theme:
            clusters[theme].append(item)

    return dict(clusters)


def cluster_by_audience(items: list[BacklogItem]) -> dict[str, list[BacklogItem]]:
    """Cluster items by audience."""
    clusters: dict[str, list[BacklogItem]] = defaultdict(list)

    for item in items:
        audience = item.audience or "unknown"
        clusters[audience].append(item)

    return dict(clusters)


def _infer_theme(idea: str) -> str:
    """Infer a rough theme from idea text."""
    if not idea:
        return "uncategorized"

    idea_lower = normalize_text(idea)
    theme_keywords = {
        "productivity": ["productivity", "效率", "time management", "focus"],
        "health": ["health", "fitness", "wellness", "diet", "sleep"],
        "technology": ["ai", "tech", "software", "app", "digital", "coding"],
        "business": ["business", "startup", "entrepreneur", "marketing", "sales"],
        "personal": ["personal", "habits", "goals", "mindset", "motivation"],
        "finance": ["money", "investing", "saving", "budget", "financial"],
    }

    for theme, keywords in theme_keywords.items():
        for keyword in keywords:
            if keyword in idea_lower:
                return theme

    return "general"


def generate_enrichment_suggestions(
    item: BacklogItem,
    gaps: list[GapAnalysis],
) -> dict[str, str]:
    """Generate enrichment field suggestions for a sparse item."""
    suggestions: dict[str, str] = {}

    # Check what the item is missing based on gaps
    item_gaps = [g for g in gaps if item.idea_id in g.affected_idea_ids]

    for gap in item_gaps:
        if gap.gap_type == "evidence" and not item.evidence:
            suggestions["evidence"] = "Add specific proof points or data supporting this idea"
        elif gap.gap_type == "freshness" and not item.why_now:
            suggestions["why_now"] = "Explain why this topic is relevant right now"
        elif gap.gap_type == "hook" and not item.potential_hook:
            suggestions["potential_hook"] = "Consider an attention-grabbing opening angle"

    # Generic suggestions for missing fields
    if not item.genericity_risk:
        suggestions["genericity_risk"] = "Consider what makes this idea feel generic vs specific"

    if not item.proof_gap_note:
        suggestions["proof_gap_note"] = "Note what additional evidence would strengthen this"

    return suggestions


