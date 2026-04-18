"""Opportunity Radar engine.

This module provides:
- SignalCluster: groups of related signals
- SignalClusterer: clusters signals by topic/keyword similarity
- ScoreCalculator: computes multi-dimensional scores for opportunities
- FreshnessManager: manages freshness state transitions
- RadarEngine: orchestrates the full ingest cycle
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from cc_deep_research.radar.models import (
    FeedbackType,
    FreshnessState,
    Opportunity,
    OpportunityScore,
    OpportunityStatus,
    OpportunityType,
    RawSignal,
    StatusHistoryEntry,
)
from cc_deep_research.radar.scanner import SourceScanner
from cc_deep_research.radar.storage import RadarStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feedback-adjusted weight modifier
# ---------------------------------------------------------------------------

_WEIGHT_PENALTY_PER_DISMISSAL = 0.85
_WEIGHT_BOOST_PER_ACTED_ON = 1.10
_MIN_MODIFIER = 0.5
_MAX_MODIFIER = 1.2


@dataclass
class FeedbackWeightModifier:
    """Multipliers applied to each scoring dimension based on feedback history."""

    strategic_relevance: float = 1.0
    novelty: float = 1.0
    urgency: float = 1.0
    evidence: float = 1.0
    business_value: float = 1.0
    workflow_fit: float = 1.0


def _compute_dimension_modifier(negative_count: int, positive_count: int) -> float:
    """Compute a single dimension modifier from feedback counts."""
    modifier = 1.0
    modifier *= (_WEIGHT_PENALTY_PER_DISMISSAL ** negative_count)
    modifier *= (_WEIGHT_BOOST_PER_ACTED_ON ** positive_count)
    return max(_MIN_MODIFIER, min(_MAX_MODIFIER, modifier))


# ---------------------------------------------------------------------------
# Keyword sets for opportunity type detection
# ---------------------------------------------------------------------------

_TYPE_KEYWORDS: dict[OpportunityType, list[str]] = {
    OpportunityType.COMPETITOR_MOVE: [
        "competitor", "rival", "competitor's", "competitors",
        "launched", "released", "announced", "new feature", "new product",
    ],
    OpportunityType.AUDIENCE_QUESTION: [
        "how to", "what is", "why does", "can i", "should i",
        "question", "ask", "faq", "help wanted", "looking for",
    ],
    OpportunityType.RISING_TOPIC: [
        "trending", "rising", "viral", "growing", "exploding",
        "surge", "spike", "increasing", "popular",
    ],
    OpportunityType.NARRATIVE_SHIFT: [
        "shift", "change", "trend", "movement", "evolution",
        "paradigm", "new era", "changing", "transforming",
    ],
    OpportunityType.LAUNCH_UPDATE_CHANGE: [
        "launch", "release", "update", "new version", "new release",
        "beta", "announcement", "introducing", "now available",
    ],
    OpportunityType.PROOF_POINT: [
        "case study", "success story", "results", "proof", "example",
        "data", "study", "research", "metrics", "performance",
    ],
    OpportunityType.RECURRING_PATTERN: [
        "every year", "annual", "seasonal", "recurring", "annual",
        "yearly", "every quarter", "regularly", "routine",
    ],
}

_STRATEGIC_KEYWORDS = [
    "competitor", "market", "industry", "strategy", "strategic",
    "opportunity", "growth", "revenue", "customer", "product",
    "feature", "launch", "release", "update", "announcement",
]

# Fallback keywords used when no strategy memory is available
_FALLBACK_KEYWORDS = _STRATEGIC_KEYWORDS


# ---------------------------------------------------------------------------
# Signal cluster
# ---------------------------------------------------------------------------


@dataclass
class SignalCluster:
    """A group of related raw signals that form a single opportunity."""

    signal_ids: list[str]
    representative_title: str = ""
    representative_summary: str = ""
    opportunity_type: OpportunityType = OpportunityType.RISING_TOPIC
    keywords: list[str] = field(default_factory=list)
    newest_signal_date: datetime | None = None

    @property
    def signal_count(self) -> int:
        return len(self.signal_ids)


# ---------------------------------------------------------------------------
# Signal clusterer
# ---------------------------------------------------------------------------


class SignalClusterer:
    """Clusters raw signals by topic similarity using keyword overlap."""

    # Minimum number of shared keywords to cluster two signals together
    MIN_SHARED_KEYWORDS = 2

    # Time window for clustering in days
    CLUSTER_WINDOW_DAYS = 7

    # Minimum signal count in a cluster
    MIN_CLUSTER_SIZE = 1

    # Stopwords to exclude from keyword extraction
    STOPWORDS = {
        "the", "and", "for", "are", "but", "not", "you", "all",
        "can", "had", "her", "was", "one", "our", "out", "has",
        "have", "been", "were", "they", "this", "that", "with",
        "from", "your", "what", "when", "where", "which", "their",
        "will", "would", "there", "could", "other", "into", "just",
        "also", "more", "only", "some", "than", "then", "them",
    }

    @staticmethod
    def _extract_keywords(title: str, summary: str | None = None) -> set[str]:
        """Extract significant keywords from title and summary.

        Args:
            title: The signal title.
            summary: Optional signal summary.

        Returns:
            Set of lowercase keywords (3+ chars, alpha-only, not stopwords).
        """
        text = f"{title} {summary or ''}".lower()
        # Split on non-alphanumeric, filter short words and stopwords
        words = re.findall(r"[a-z]+", text)
        return {
            w for w in words
            if len(w) >= 3 and w not in SignalClusterer.STOPWORDS
        }

    @staticmethod
    def _jaccard_similarity(set1: set[str], set2: set[str]) -> float:
        """Compute Jaccard similarity between two sets.

        Args:
            set1: First set of keywords.
            set2: Second set of keywords.

        Returns:
            Jaccard similarity score (0.0 to 1.0).
        """
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    @staticmethod
    def _cosine_similarity(set1: set[str], set2: set[str]) -> float:
        """Compute simple cosine-like similarity between two sets.

        Uses shared / sqrt(len1 * len2) formula.

        Args:
            set1: First set of keywords.
            set2: Second set of keywords.

        Returns:
            Similarity score (0.0 to 1.0).
        """
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        denom = math.sqrt(len(set1) * len(set2))
        return intersection / denom if denom > 0 else 0.0

    def cluster_signals(self, signals: list[RawSignal]) -> list[SignalCluster]:
        """Cluster signals by topic similarity within a time window.

        Uses greedy clustering: each signal is assigned to the first cluster
        where it meets the similarity threshold. If no cluster fits, creates
        a new cluster.

        Args:
            signals: List of RawSignals to cluster.

        Returns:
            List of SignalCluster objects.
        """
        if not signals:
            return []

        # Parse published_at for each signal
        signals_with_time = []
        now = datetime.now(tz=UTC)
        window = timedelta(days=self.CLUSTER_WINDOW_DAYS)

        for sig in signals:
            pub_date = None
            if sig.published_at:
                try:
                    pub_date = datetime.fromisoformat(sig.published_at)
                    if pub_date.tzinfo is None:
                        pub_date = pub_date.replace(tzinfo=UTC)
                except ValueError:
                    pass

            # Default to now if no date
            if pub_date is None:
                pub_date = now

            signals_with_time.append((sig, pub_date))

        # Sort by date descending (newest first)
        signals_with_time.sort(key=lambda x: x[1], reverse=True)

        clusters: list[SignalCluster] = []

        for sig, pub_date in signals_with_time:
            keywords = self._extract_keywords(sig.title, sig.summary)
            assigned = False

            for cluster in clusters:
                # Check time window
                if cluster.newest_signal_date and (pub_date - cluster.newest_signal_date).days > self.CLUSTER_WINDOW_DAYS:
                    continue

                # Check similarity with cluster representative keywords
                cluster_keywords = set(cluster.keywords)
                similarity = self._cosine_similarity(keywords, cluster_keywords)

                if similarity >= 0.15:  # Similarity threshold
                    cluster.signal_ids.append(sig.id)
                    # Update cluster keywords with union
                    cluster.keywords = list(set(cluster.keywords) | keywords)
                    # Update newest date if this is newer
                    if cluster.newest_signal_date is None or pub_date > cluster.newest_signal_date:
                        cluster.newest_signal_date = pub_date
                    assigned = True
                    break

            if not assigned:
                # Create new cluster
                clusters.append(
                    SignalCluster(
                        signal_ids=[sig.id],
                        representative_title=sig.title,
                        representative_summary=sig.summary or "",
                        keywords=list(keywords),
                        newest_signal_date=pub_date,
                    )
                )

        # Post-process: pick representative title from highest-score signal
        for cluster in clusters:
            self._pick_representative(signals, cluster)

        # Filter out clusters that are too small
        return [c for c in clusters if len(c.signal_ids) >= self.MIN_CLUSTER_SIZE]

    def _pick_representative(self, signals: list[RawSignal], cluster: SignalCluster) -> None:
        """Pick the best representative title and summary for a cluster.

        Uses signal with the most complete title as representative.

        Args:
            signals: All signals (to look up by id).
            cluster: The cluster to update.
        """
        signal_map = {s.id: s for s in signals}
        cluster_signals = [signal_map[sid] for sid in cluster.signal_ids if sid in signal_map]

        if not cluster_signals:
            return

        # Pick signal with longest title as representative
        best = max(cluster_signals, key=lambda s: len(s.title))
        cluster.representative_title = best.title
        cluster.representative_summary = best.summary or ""

        # Determine opportunity type based on keywords
        cluster.opportunity_type = self._detect_opportunity_type(cluster.keywords)

    @staticmethod
    def _detect_opportunity_type(keywords: list[str]) -> OpportunityType:
        """Detect the opportunity type based on cluster keywords.

        Args:
            keywords: Keywords from the cluster.

        Returns:
            Detected OpportunityType.
        """
        keyword_set = {k.lower() for k in keywords}
        scores: dict[OpportunityType, int] = {}

        for opp_type, type_keywords in _TYPE_KEYWORDS.items():
            score = sum(1 for kw in type_keywords if kw in keyword_set)
            if score > 0:
                scores[opp_type] = score

        if not scores:
            return OpportunityType.RISING_TOPIC

        return max(scores, key=scores.get)  # type: ignore


# ---------------------------------------------------------------------------
# Score calculator
# ---------------------------------------------------------------------------


class ScoreCalculator:
    """Computes multi-dimensional scores for opportunities."""

    # Weights for each dimension
    WEIGHTS = {
        "strategic_relevance": 0.30,
        "novelty": 0.10,
        "urgency": 0.15,
        "evidence": 0.15,
        "business_value": 0.20,
        "workflow_fit": 0.10,
    }

    def __init__(
        self,
        strategy_memory: Any = None,
    ) -> None:
        """Initialize the calculator with optional strategy context.

        Args:
            strategy_memory: Optional StrategyMemory for strategy-aware scoring.
        """
        self._strategy_memory = strategy_memory
        self._strategic_keywords = self._extract_keywords_from_strategy(strategy_memory)

    def _extract_keywords_from_strategy(self, memory: Any) -> list[str]:
        """Extract strategic keywords from StrategyMemory or fall back to defaults."""
        if memory is None:
            return _FALLBACK_KEYWORDS

        from cc_deep_research.content_gen.models import ContentPillar

        keywords: set[str] = set()
        keyword_set = {k.lower() for k in _FALLBACK_KEYWORDS}

        # Pull niche words
        if hasattr(memory, "niche") and memory.niche:
            niche_words = re.findall(r"[a-z]+", memory.niche.lower())
            keywords.update(w for w in niche_words if len(w) >= 3)

        # Pull content pillar words
        if hasattr(memory, "content_pillars") and memory.content_pillars:
            for pillar in memory.content_pillars:
                if isinstance(pillar, ContentPillar):
                    kw = re.findall(r"[a-z]+", pillar.name.lower())
                    keywords.update(w for w in kw if len(w) >= 3)
                    if pillar.description:
                        desc_words = re.findall(r"[a-z]+", pillar.description.lower())
                        keywords.update(w for w in desc_words if len(w) >= 3)
                elif isinstance(pillar, dict):
                    name = pillar.get("name", "")
                    kw = re.findall(r"[a-z]+", name.lower())
                    keywords.update(w for w in kw if len(w) >= 3)

        # Pull forbidden topics so we can suppress them
        if hasattr(memory, "forbidden_topics") and memory.forbidden_topics:
            for topic in memory.forbidden_topics:
                words = re.findall(r"[a-z]+", topic.lower())
                keywords.update(w for w in words if len(w) >= 3)

        # If we got nothing meaningful, fall back
        if not keywords:
            return _FALLBACK_KEYWORDS

        return list(keywords)

    def _score_strategic_relevance(self, opportunity: Opportunity, signals: list[RawSignal]) -> float:
        """Score strategic relevance based on keyword matching.

        Args:
            opportunity: The Opportunity.
            signals: Signals in the cluster.

        Returns:
            Score from 0-100.
        """
        text = f"{opportunity.title} {opportunity.summary}".lower()
        keyword_set = {k.lower() for k in self._strategic_keywords}
        matches = sum(1 for kw in keyword_set if kw in text)
        return min(100.0, matches * 35)

    def calculate(
        self,
        opportunity: Opportunity,
        signals: list[RawSignal],
        cluster: SignalCluster,
        weight_modifier: FeedbackWeightModifier | None = None,
    ) -> tuple[OpportunityScore, str]:
        """Calculate all scoring dimensions for an opportunity.

        Args:
            opportunity: The Opportunity being scored.
            signals: All RawSignals in the opportunity's cluster.
            cluster: The SignalCluster for this opportunity.
            weight_modifier: Optional feedback-based weight adjustments.

        Returns:
            A tuple of (OpportunityScore, human-readable explanation).
        """
        modifier = weight_modifier or FeedbackWeightModifier()
        strategic = self._score_strategic_relevance(opportunity, signals)
        novelty = self._score_novelty(signals)
        urgency = self._score_urgency(signals)
        evidence = self._score_evidence(signals, cluster)
        business_value = self._score_business_value(opportunity)
        workflow_fit = self._score_workflow_fit(opportunity, signals)

        total = (
            strategic * self.WEIGHTS["strategic_relevance"] * modifier.strategic_relevance
            + novelty * self.WEIGHTS["novelty"] * modifier.novelty
            + urgency * self.WEIGHTS["urgency"] * modifier.urgency
            + evidence * self.WEIGHTS["evidence"] * modifier.evidence
            + business_value * self.WEIGHTS["business_value"] * modifier.business_value
            + workflow_fit * self.WEIGHTS["workflow_fit"] * modifier.workflow_fit
        )

        score = OpportunityScore(
            opportunity_id=opportunity.id,
            strategic_relevance_score=strategic,
            novelty_score=novelty,
            urgency_score=urgency,
            evidence_score=evidence,
            business_value_score=business_value,
            workflow_fit_score=workflow_fit,
            total_score=total,
            explanation=None,  # Set below
        )

        explanation = self._generate_explanation(
            opportunity, signals, cluster,
            strategic, novelty, urgency, evidence, business_value, workflow_fit, total,
        )
        score.explanation = explanation

        return score, explanation

    def _score_novelty(self, signals: list[RawSignal]) -> float:
        """Score novelty based on how recent the newest signal is.

        Args:
            signals: Signals in the cluster.

        Returns:
            Score from 0-100 (newer = higher).
        """
        now = datetime.now(tz=UTC)
        newest = None

        for sig in signals:
            if sig.published_at:
                try:
                    pub = datetime.fromisoformat(sig.published_at)
                    if pub.tzinfo is None:
                        pub = pub.replace(tzinfo=UTC)
                    if newest is None or pub > newest:
                        newest = pub
                except ValueError:
                    pass

        if newest is None:
            return 50.0  # Unknown age = medium score

        age_hours = (now - newest).total_seconds() / 3600

        if age_hours <= 2:
            return 95.0
        elif age_hours <= 12:
            return 80.0
        elif age_hours <= 24:
            return 65.0
        elif age_hours <= 48:
            return 50.0
        elif age_hours <= 72:
            return 35.0
        else:
            return 20.0

    def _score_urgency(self, signals: list[RawSignal]) -> float:
        """Score urgency based on source type and recency.

        News sources get higher urgency. Recent items get higher urgency.

        Args:
            signals: Signals in the cluster.

        Returns:
            Score from 0-100.
        """
        if not signals:
            return 30.0

        # Use newest signal date for urgency
        now = datetime.now(tz=UTC)
        newest = None

        for sig in signals:
            if sig.published_at:
                try:
                    pub = datetime.fromisoformat(sig.published_at)
                    if pub.tzinfo is None:
                        pub = pub.replace(tzinfo=UTC)
                    if newest is None or pub > newest:
                        newest = pub
                except ValueError:
                    pass

        if newest is None:
            return 30.0

        age_hours = (now - newest).total_seconds() / 3600

        # Count source types
        source_types = Counter(s.normalized_type for s in signals if s.normalized_type)
        is_news_heavy = source_types.get("news", 0) / len(signals) >= 0.5

        base_score = 50.0
        if age_hours <= 6:
            base_score = 90.0
        elif age_hours <= 24:
            base_score = 70.0
        elif age_hours <= 48:
            base_score = 50.0
        else:
            base_score = 30.0

        if is_news_heavy:
            base_score = min(100.0, base_score * 1.3)

        return base_score

    def _score_evidence(self, signals: list[RawSignal], cluster: SignalCluster) -> float:
        """Score evidence based on number of signals (more = higher credibility).

        Args:
            signals: Signals in the cluster.
            cluster: The signal cluster.

        Returns:
            Score from 0-100.
        """
        count = len(signals)
        if count >= 5:
            return 90.0
        elif count == 4:
            return 80.0
        elif count == 3:
            return 70.0
        elif count == 2:
            return 55.0
        else:
            return 40.0

    def _score_business_value(self, opportunity: Opportunity) -> float:
        """Score business value based on opportunity type.

        Args:
            opportunity: The Opportunity.

        Returns:
            Score from 0-100.
        """
        type_scores: dict[OpportunityType, float] = {
            OpportunityType.COMPETITOR_MOVE: 85.0,
            OpportunityType.AUDIENCE_QUESTION: 60.0,
            OpportunityType.RISING_TOPIC: 75.0,
            OpportunityType.NARRATIVE_SHIFT: 70.0,
            OpportunityType.LAUNCH_UPDATE_CHANGE: 80.0,
            OpportunityType.PROOF_POINT: 65.0,
            OpportunityType.RECURRING_PATTERN: 50.0,
        }
        return type_scores.get(opportunity.opportunity_type, 50.0)

    def _score_workflow_fit(
        self,
        opportunity: Opportunity,
        signals: list[RawSignal],
    ) -> float:
        """Score workflow fit based on opportunity completeness.

        More complete opportunities (with why_it_matters, recommended_action)
        and those with source URLs score higher.

        Args:
            opportunity: The Opportunity.
            signals: Signals in the cluster.

        Returns:
            Score from 0-100.
        """
        score = 50.0
        if opportunity.why_it_matters:
            score += 15.0
        if opportunity.recommended_action:
            score += 15.0
        # Check if any signal has a URL
        has_url = any(s.url for s in signals)
        if has_url:
            score += 10.0
        return min(100.0, score)

    def _generate_explanation(
        self,
        opportunity: Opportunity,
        signals: list[RawSignal],
        cluster: SignalCluster,
        strategic: float,
        novelty: float,
        urgency: float,
        evidence: float,
        business_value: float,
        workflow_fit: float,
        total: float,
    ) -> str:
        """Generate a human-readable explanation of the score.

        Args:
            opportunity: The Opportunity.
            signals: Signals in the cluster.
            cluster: The signal cluster.
            Scores for each dimension.
            total: The total weighted score.

        Returns:
            A human-readable explanation string.
        """
        parts: list[str] = []

        # Strategic relevance
        if strategic >= 70:
            parts.append("Strong strategic fit — contains key industry and market terms.")
        elif strategic >= 40:
            parts.append("Moderate strategic relevance.")
        else:
            parts.append("Low strategic keyword density.")

        # Novelty
        if novelty >= 80:
            parts.append("Very recent discovery — high novelty.")
        elif novelty >= 50:
            parts.append("Moderately novel content.")
        else:
            parts.append("Less novel or older content.")

        # Urgency
        if urgency >= 70:
            parts.append("High urgency — timely topic likely to resonate now.")
        elif urgency >= 40:
            parts.append("Moderate urgency.")
        else:
            parts.append("Lower urgency — less time-sensitive.")

        # Evidence
        count = len(signals)
        if count >= 4:
            parts.append(f"Strong evidence base — {count} signals corroborate this.")
        elif count >= 2:
            parts.append(f"Moderate evidence — {count} signals in cluster.")
        else:
            parts.append("Limited evidence — single signal source.")

        # Business value
        bv_label = "high" if business_value >= 70 else "moderate" if business_value >= 50 else "lower"
        parts.append(f"Business value is {bv_label} for this opportunity type.")

        # Workflow fit
        if workflow_fit >= 70:
            parts.append("Highly actionable — good fit for immediate workflow.")
        elif workflow_fit >= 50:
            parts.append("Moderately actionable.")
        else:
            parts.append("Lower workflow fit — may need more context.")

        parts.append(f"Total score: {total:.1f}/100.")

        return " ".join(parts)


# ---------------------------------------------------------------------------
# Freshness manager
# ---------------------------------------------------------------------------


class FreshnessManager:
    """Manages freshness state transitions for opportunities."""

    # Thresholds in hours
    FRESH_THRESHOLD_HOURS = 24
    STALE_THRESHOLD_HOURS = 72
    NEW_THRESHOLD_HOURS = 6

    def compute_freshness_state(
        self,
        opportunity: Opportunity,
        signals: list[RawSignal],
    ) -> FreshnessState:
        """Compute the freshness state for an opportunity.

        Freshness is based on:
        - NEW: opportunity created within last 6h
        - FRESH: newest signal within 24h
        - STALE: newest signal between 24h and 72h
        - EXPIRED: newest signal older than 72h

        Args:
            opportunity: The Opportunity.
            signals: All signals linked to the opportunity.

        Returns:
            The computed FreshnessState.
        """
        now = datetime.now(tz=UTC)

        # Check if opportunity is still very new
        try:
            created = datetime.fromisoformat(opportunity.first_detected_at)
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            age_hours = (now - created).total_seconds() / 3600
            if age_hours <= self.NEW_THRESHOLD_HOURS:
                return FreshnessState.NEW
        except ValueError:
            pass

        # Find newest signal
        newest = None
        for sig in signals:
            if sig.published_at:
                try:
                    pub = datetime.fromisoformat(sig.published_at)
                    if pub.tzinfo is None:
                        pub = pub.replace(tzinfo=UTC)
                    if newest is None or pub > newest:
                        newest = pub
                except ValueError:
                    pass

        if newest is None:
            # No signals with dates = stale
            return FreshnessState.STALE

        age_hours = (now - newest).total_seconds() / 3600

        if age_hours <= self.FRESH_THRESHOLD_HOURS:
            return FreshnessState.FRESH
        elif age_hours <= self.STALE_THRESHOLD_HOURS:
            return FreshnessState.STALE
        else:
            return FreshnessState.EXPIRED

    def apply_freshness_decay(self, opportunity: Opportunity, signals: list[RawSignal]) -> Opportunity:
        """Update opportunity freshness_state based on linked signals.

        Args:
            opportunity: The Opportunity to update.
            signals: All signals linked to the opportunity.

        Returns:
            The updated Opportunity (may be the same object or a new one).
        """
        new_state = self.compute_freshness_state(opportunity, signals)
        if opportunity.freshness_state != new_state:
            opportunity.freshness_state = new_state
        return opportunity


# ---------------------------------------------------------------------------
# Radar Engine
# ---------------------------------------------------------------------------


class RadarEngine:
    """Orchestrates the full opportunity ingestion and scoring cycle."""

    def __init__(
        self,
        store: RadarStore | None = None,
        scanner: SourceScanner | None = None,
        strategy_memory: Any | None = None,
    ) -> None:
        """Initialize the engine.

        Args:
            store: RadarStore to use. Defaults to new RadarStore.
            scanner: SourceScanner to use. Defaults to new SourceScanner.
            strategy_memory: Optional StrategyMemory for strategy-aware scoring.
        """
        self._store = store or RadarStore()
        self._scanner = scanner or SourceScanner(self._store)
        self._clusterer = SignalClusterer()
        self._scorer = ScoreCalculator(strategy_memory=strategy_memory)
        self._freshness = FreshnessManager()

    def _compute_feedback_adjustment(
        self,
        opportunity_type: str,
    ) -> FeedbackWeightModifier:
        """Compute feedback-based weight modifiers for an opportunity type.

        Args:
            opportunity_type: The type of opportunity being scored.

        Returns:
            FeedbackWeightModifier with per-dimension multipliers.
        """
        counts = self._store.get_feedback_counts(opportunity_type=opportunity_type)
        dismissed = counts.get(FeedbackType.DISMISSED, 0) + counts.get(FeedbackType.IGNORED, 0)
        acted_on = (
            counts.get(FeedbackType.ACTED_ON, 0)
            + counts.get(FeedbackType.CONVERTED_TO_RESEARCH, 0)
            + counts.get(FeedbackType.CONVERTED_TO_CONTENT, 0)
        )
        base = _compute_dimension_modifier(dismissed, acted_on)
        return FeedbackWeightModifier(
            workflow_fit=base,
            business_value=max(0.8, base + 0.1),
            novelty=max(0.85, base),
        )

    # -- Deduplication --------------------------------------------------------

    def deduplicate_signals(self, new_signals: list[RawSignal]) -> list[RawSignal]:
        """Filter out signals that are duplicates of existing ones.

        A signal is considered a duplicate if:
        1. A signal with the same content_hash already exists (from same source)
        2. A signal with the same external_id already exists (from same source)

        Args:
            new_signals: Signals to check for duplicates.

        Returns:
            Only the signals that are not duplicates.
        """
        existing_signals = self._store.load_signals().signals
        existing_by_source: dict[str, set[str]] = {}
        existing_hashes: set[str] = set()

        for sig in existing_signals:
            source_external_ids = existing_by_source.setdefault(sig.source_id, set())
            if sig.external_id:
                source_external_ids.add(sig.external_id)
            if sig.content_hash:
                existing_hashes.add(sig.content_hash)

        unique_signals: list[RawSignal] = []
        seen_hashes: set[str] = set()

        for sig in new_signals:
            source_external_ids = existing_by_source.setdefault(sig.source_id, set())

            # Skip if we already decided to skip this hash in this batch
            if sig.content_hash and sig.content_hash in seen_hashes:
                continue

            # Check against existing signals
            is_dup = (
                (sig.content_hash and sig.content_hash in existing_hashes)
                or (sig.external_id and sig.external_id in source_external_ids)
            )

            if not is_dup:
                unique_signals.append(sig)
                if sig.content_hash:
                    seen_hashes.add(sig.content_hash)
                    existing_hashes.add(sig.content_hash)
                if sig.external_id:
                    source_external_ids.add(sig.external_id)

        return unique_signals

    # -- Ingest cycle ---------------------------------------------------------

    def run_ingest_cycle(self) -> dict[str, Any]:
        """Run the full ingest cycle: scan, dedupe, cluster, score, store.

        Returns:
            A summary dict with counts of signals, clusters, and opportunities.
        """
        # 1. Scan all due sources
        scanned_signals = self._scanner.scan_due_sources()

        if not scanned_signals:
            return {
                "signals_scanned": 0,
                "signals_new": 0,
                "clusters_created": 0,
                "opportunities_created": 0,
                "opportunities_updated": 0,
            }

        # 2. Deduplicate
        new_signals = self.deduplicate_signals(scanned_signals)

        if not new_signals:
            return {
                "signals_scanned": len(scanned_signals),
                "signals_new": 0,
                "clusters_created": 0,
                "opportunities_created": 0,
                "opportunities_updated": 0,
            }

        # 3. Persist new signals
        self._store.add_signals(new_signals)

        # 4. Cluster signals (new + existing recent)
        all_signals = self._store.load_signals().signals

        # Get signals from last 7 days for clustering
        cutoff = datetime.now(tz=UTC) - timedelta(days=7)
        recent_signals = []
        for sig in all_signals:
            if sig.discovered_at:
                try:
                    disc = datetime.fromisoformat(sig.discovered_at)
                    if disc.tzinfo is None:
                        disc = disc.replace(tzinfo=UTC)
                    if disc >= cutoff:
                        recent_signals.append(sig)
                except ValueError:
                    pass

        clusters = self._clusterer.cluster_signals(recent_signals)

        # 5. Create/update opportunities
        opp_created = 0
        opp_updated = 0

        for cluster in clusters:
            is_new = self._process_cluster(cluster, recent_signals)
            if is_new:
                opp_created += 1
            else:
                opp_updated += 1

        return {
            "signals_scanned": len(scanned_signals),
            "signals_new": len(new_signals),
            "clusters_created": len(clusters),
            "opportunities_created": opp_created,
            "opportunities_updated": opp_updated,
        }

    def _process_cluster(
        self,
        cluster: SignalCluster,
        all_signals: list[RawSignal],
    ) -> bool:
        """Process a single signal cluster into an opportunity.

        Args:
            cluster: The signal cluster.
            all_signals: All signals (for looking up cluster members).

        Returns:
            True if a new opportunity was created, False if an existing one was updated.
        """
        signal_map = {s.id: s for s in all_signals}
        cluster_signals = [signal_map[sid] for sid in cluster.signal_ids if sid in signal_map]

        # Check if an opportunity already exists for this cluster
        # Heuristic: check if any signal in cluster is already linked to an opportunity
        existing_opp_id: str | None = None
        for sig_id in cluster.signal_ids:
            linked_opps = self._store.get_opportunity_ids_for_signal(sig_id)
            if linked_opps:
                existing_opp_id = linked_opps[0]
                break

        if existing_opp_id:
            # Update existing opportunity
            self._update_opportunity_from_cluster(existing_opp_id, cluster, cluster_signals)
            return False
        else:
            # Create new opportunity
            self._create_opportunity_from_cluster(cluster, cluster_signals)
            return True

    def _create_opportunity_from_cluster(
        self,
        cluster: SignalCluster,
        signals: list[RawSignal],
    ) -> Opportunity:
        """Create a new opportunity from a signal cluster.

        Args:
            cluster: The signal cluster.
            signals: The signals in the cluster.

        Returns:
            The created Opportunity.
        """
        # Build why_it_matters
        why = self._build_why_it_matters(cluster, signals)

        # Build recommended_action
        action = self._build_recommended_action(cluster)

        opp = Opportunity(
            title=cluster.representative_title,
            summary=cluster.representative_summary,
            opportunity_type=cluster.opportunity_type,
            why_it_matters=why,
            recommended_action=action,
        )

        self._store.add_opportunity(opp)

        # Record initial status history entry
        self._store.add_status_history_entry(
            StatusHistoryEntry(
                opportunity_id=opp.id,
                previous_status=OpportunityStatus.NEW,
                new_status=OpportunityStatus.NEW,
                reason="opportunity_created",
            )
        )

        # Link all signals
        for sig_id in cluster.signal_ids:
            self._store.link_signal_to_opportunity(
                opportunity_id=opp.id,
                raw_signal_id=sig_id,
                link_reason="same_topic",
            )

        # Score and update (with feedback-based weight adjustment)
        modifier = self._compute_feedback_adjustment(opp.opportunity_type.value)
        score, _ = self._scorer.calculate(opp, signals, cluster, modifier)
        self._store.upsert_score(score)

        # Apply freshness
        opp = self._freshness.apply_freshness_decay(opp, signals)
        self._store.update_opportunity(opp.id, {
            "total_score": score.total_score,
            "priority_label": score.priority_label,
            "freshness_state": opp.freshness_state,
        })

        return opp

    def _update_opportunity_from_cluster(
        self,
        opportunity_id: str,
        cluster: SignalCluster,
        signals: list[RawSignal],
    ) -> Opportunity:
        """Update an existing opportunity with new signals from a cluster.

        Args:
            opportunity_id: The existing opportunity id.
            cluster: The signal cluster.
            signals: The signals in the cluster.

        Returns:
            The updated Opportunity.
        """
        opp = self._store.get_opportunity(opportunity_id)
        if opp is None:
            raise ValueError(f"Opportunity {opportunity_id} not found")

        # Link any new signals
        existing_sig_ids = set(self._store.get_signal_ids_for_opportunity(opportunity_id))
        for sig_id in cluster.signal_ids:
            if sig_id not in existing_sig_ids:
                self._store.link_signal_to_opportunity(
                    opportunity_id=opportunity_id,
                    raw_signal_id=sig_id,
                    link_reason="same_topic",
                )

        # Re-score (with feedback-based weight adjustment)
        modifier = self._compute_feedback_adjustment(opp.opportunity_type.value)
        score, _ = self._scorer.calculate(opp, signals, cluster, modifier)
        self._store.upsert_score(score)

        # Update opportunity
        opp = self._freshness.apply_freshness_decay(opp, signals)
        self._store.update_opportunity(opportunity_id, {
            "total_score": score.total_score,
            "priority_label": score.priority_label,
            "freshness_state": opp.freshness_state,
            "last_detected_at": datetime.now(tz=UTC).isoformat(),
        })

        return self._store.get_opportunity(opportunity_id)  # type: ignore

    def _build_why_it_matters(self, cluster: SignalCluster, signals: list[RawSignal]) -> str:
        """Build a 'why it matters' string from cluster info.

        Args:
            cluster: The signal cluster.
            signals: Signals in the cluster.

        Returns:
            A human-readable explanation of strategic significance.
        """
        count = len(signals)
        type_label = cluster.opportunity_type.value.replace("_", " ")

        source_types = Counter(s.normalized_type for s in signals if s.normalized_type)
        top_source = source_types.most_common(1)[0][0] if source_types else "source"

        parts = [
            f"This {type_label} was detected from {count} signal{'s' if count > 1 else ''}",
            f"(primarily from {top_source}s)",
        ]

        if cluster.keywords:
            top_keywords = cluster.keywords[:4]
            parts.append(f"centered around: {', '.join(top_keywords)}.")

        return " ".join(parts)

    def _build_recommended_action(self, cluster: SignalCluster) -> str:
        """Build a recommended action string.

        Args:
            cluster: The signal cluster.

        Returns:
            A suggested next step.
        """
        type_actions: dict[OpportunityType, str] = {
            OpportunityType.COMPETITOR_MOVE: "Investigate competitor's new feature and assess your response strategy.",
            OpportunityType.AUDIENCE_QUESTION: "Create content that directly addresses this audience question.",
            OpportunityType.RISING_TOPIC: "Monitor closely and prepare to create content if the trend continues.",
            OpportunityType.NARRATIVE_SHIFT: "Evaluate how this shift affects your market positioning.",
            OpportunityType.LAUNCH_UPDATE_CHANGE: "Review the announcement and determine if it affects your roadmap.",
            OpportunityType.PROOF_POINT: "Incorporate this data into your content and sales materials.",
            OpportunityType.RECURRING_PATTERN: "Plan ahead for this recurring event in your content calendar.",
        }
        return type_actions.get(cluster.opportunity_type, "Review and determine appropriate next steps.")

    # -- Rescore --------------------------------------------------------------

    def rescore_opportunity(self, opportunity_id: str) -> Opportunity | None:
        """Rescore and refresh an existing opportunity.

        Args:
            opportunity_id: The opportunity to rescore.

        Returns:
            The updated Opportunity or None if not found.
        """
        opp = self._store.get_opportunity(opportunity_id)
        if opp is None:
            return None

        signal_ids = self._store.get_signal_ids_for_opportunity(opportunity_id)
        signals = [self._store.get_signal(sid) for sid in signal_ids]
        signals = [s for s in signals if s is not None]

        if not signals:
            return opp

        # Create a temporary cluster for scoring
        keywords: list[str] = []
        for sig in signals:
            kws = SignalClusterer._extract_keywords(sig.title, sig.summary)
            keywords.extend(kws)

        cluster = SignalCluster(
            signal_ids=[s.id for s in signals],
            representative_title=opp.title,
            representative_summary=opp.summary,
            opportunity_type=opp.opportunity_type,
            keywords=list(set(keywords)),
        )

        modifier = self._compute_feedback_adjustment(opp.opportunity_type.value)
        score, explanation = self._scorer.calculate(opp, signals, cluster, modifier)
        self._store.upsert_score(score)

        opp = self._freshness.apply_freshness_decay(opp, signals)
        self._store.update_opportunity(opportunity_id, {
            "total_score": score.total_score,
            "priority_label": score.priority_label,
            "freshness_state": opp.freshness_state,
        })

        return self._store.get_opportunity(opportunity_id)
