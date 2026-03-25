"""Theme detection from research queries."""

from __future__ import annotations

import re
from typing import Any

from .models import DetectionResult, ResearchTheme


class ThemeDetector:
    """Pattern-based theme detection with confidence scoring."""

    # Pattern definitions for each theme
    # Each pattern has the pattern string and a weight
    PATTERNS: dict[ResearchTheme, list[tuple[str, float]]] = {
        ResearchTheme.TRIP_PLANNING: [
            (r"\btrip\s+to\b", 0.9),
            (r"\bvisit\s+\w+\b", 0.7),
            (r"\bitinerary\b", 0.9),
            (r"\bvacation\b", 0.8),
            (r"\bhotels?\s+(in|near|at)\b", 0.85),
            (r"\bflights?\s+(to|from)\b", 0.8),
            (r"\btravel\s+(to|guide|tips)\b", 0.75),
            (r"\bsight(s|seeing)\b", 0.7),
            (r"\btourist|\battractions?\b", 0.7),
            (r"\bthings\s+to\s+do\s+(in|at)\b", 0.85),
            (r"\bbest\s+time\s+to\s+visit\b", 0.85),
            (r"\btravel\s+insurance\b", 0.6),
            (r"\bpassport|\bvisa\b", 0.5),
            (r"\bairbnb|\bbooking\b", 0.6),
            (r"\brestaurants?\s+(in|near)\b", 0.5),
        ],
        ResearchTheme.RESOURCES_GATHERING: [
            (r"\blist\s+of\b", 0.8),
            (r"\bresources?\s+for\b", 0.85),
            (r"\btools?\s+for\b", 0.8),
            (r"\bbest\s+websites?\b", 0.75),
            (r"\btop\s+\d+\s+", 0.5),
            (r"\bcurated\s+list\b", 0.8),
            (r"\bcollection\s+of\b", 0.7),
            (r"\bdirectory\b", 0.7),
            (r"\bawesome\s+\w+\b", 0.75),  # e.g., "awesome python"
            (r"\bgithub\s+repo", 0.6),
            (r"\bopen\s+source\b", 0.4),
            (r"\blibraries?\s+(for|to)\b", 0.65),
            (r"\bframeworks?\s+(for|to)\b", 0.65),
            (r"\balternatives?\s+to\b", 0.5),
            (r"\bcompar(e|ison)\b", 0.4),
        ],
        ResearchTheme.BUSINESS_DUE_DILIGENCE: [
            (r"\bcompany\s+analysis\b", 0.9),
            (r"\binvestment\b", 0.7),
            (r"\bacquire\b", 0.8),
            (r"\bdue\s+diligence\b", 0.95),
            (r"\bfinancial\s+(statements?|health|analysis)\b", 0.85),
            (r"\brevenue\b", 0.5),
            (r"\bvaluation\b", 0.8),
            (r"\b(acqui|hiring|m&a)\b", 0.7),
            (r"\bcompany\s+(profile|overview|background)\b", 0.75),
            (r"\bstock\s+(price|analysis|performance)\b", 0.7),
            (r"\bsec\s+filing", 0.85),
            (r"\b10-?k\b", 0.8),
            (r"\bannual\s+report\b", 0.7),
            (r"\bboard\s+of\s+directors\b", 0.6),
            (r"\bexecutive\s+team\b", 0.55),
            (r"\bfunding\s+(round|history)\b", 0.7),
        ],
        ResearchTheme.MARKET_RESEARCH: [
            (r"\bmarket\s+(size|share|analysis|research)\b", 0.9),
            (r"\bcompetitors?\b", 0.8),
            (r"\bindustry\s+analysis\b", 0.85),
            (r"\bcompetitive\s+(landscape|analysis)\b", 0.9),
            (r"\bmarket\s+trends?\b", 0.8),
            (r"\btam\b", 0.85),  # Total Addressable Market
            (r"\bsam\b", 0.85),  # Serviceable Addressable Market
            (r"\bsom\b", 0.85),  # Serviceable Obtainable Market
            (r"\bmarket\s+segment", 0.75),
            (r"\btarget\s+audience\b", 0.6),
            (r"\bcustomer\s+(persona|segment|profile)\b", 0.65),
            (r"\bindustry\s+(report|outlook|forecast)\b", 0.8),
            (r"\bswot\s+analysis\b", 0.7),
            (r"\bporter'?s?\s+five\b", 0.8),
            (r"\bgrowth\s+rate\b", 0.6),
        ],
        ResearchTheme.BUSINESS_IDEA_GENERATION: [
            (r"\bbusiness\s+ideas?\b", 0.95),
            (r"\bstartup\s+ideas?\b", 0.9),
            (r"\bside\s+hustle\b", 0.9),
            (r"\bentrepreneur", 0.6),
            (r"\bpassive\s+income\b", 0.75),
            (r"\bmake\s+money\b", 0.6),
            (r"\bbusiness\s+opportunit", 0.75),
            (r"\bprofitable\s+(business|ideas)\b", 0.8),
            (r"\bnew\s+venture\b", 0.7),
            (r"\bbusiness\s+model\b", 0.5),
            (r"\bmonetize\b", 0.6),
            (r"\bsaas\s+ideas?\b", 0.8),
            (r"\bmicro\s+saas\b", 0.85),
            (r"\bfreelance\s+ideas?\b", 0.7),
            (r"\be?commerce\s+ideas?\b", 0.75),
        ],
        ResearchTheme.CONTENT_CREATION: [
            (r"\bblog\s+post\b", 0.85),
            (r"\bcontent\s+ideas?\b", 0.8),
            (r"\bvideo\s+script\b", 0.85),
            (r"\barticle\s+outline\b", 0.85),
            (r"\bcontent\s+strategy\b", 0.8),
            (r"\byoutube\s+(video|channel|ideas)\b", 0.8),
            (r"\bsocial\s+media\s+(post|content|ideas)\b", 0.75),
            (r"\bnewsletter\s+(ideas|content|topics)\b", 0.8),
            (r"\bpodcast\s+(topics|ideas|episode)\b", 0.8),
            (r"\bwrite\s+(about|on)\b", 0.5),
            (r"\bcontent\s+calendar\b", 0.7),
            (r"\beditorial\s+plan\b", 0.75),
            (r"\bseo\s+(keywords|topics|content)\b", 0.6),
            (r"\bheadline\s+ideas\b", 0.7),
            (r"\bthumbnail\s+ideas\b", 0.65),
        ],
        ResearchTheme.GENERAL: [
            # General research has no strong patterns - it's the fallback
        ],
    }

    def __init__(self, *, confidence_threshold: float = 0.6) -> None:
        """Initialize the theme detector.

        Args:
            confidence_threshold: Minimum confidence to accept a detection.
        """
        self._confidence_threshold = confidence_threshold
        self._compiled_patterns: dict[ResearchTheme, list[tuple[re.Pattern[str], float]]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for efficiency."""
        for theme, patterns in self.PATTERNS.items():
            self._compiled_patterns[theme] = [
                (re.compile(p, re.IGNORECASE), weight) for p, weight in patterns
            ]

    def detect(self, query: str) -> DetectionResult:
        """Detect the most likely research theme from a query.

        Args:
            query: The research query to analyze.

        Returns:
            DetectionResult with the detected theme and confidence score.
        """
        query_lower = query.lower()
        scores: dict[ResearchTheme, float] = {}
        matched_by_theme: dict[ResearchTheme, list[str]] = {}

        # Score each theme
        for theme, patterns in self._compiled_patterns.items():
            if not patterns:
                scores[theme] = 0.0
                matched_by_theme[theme] = []
                continue

            theme_score = 0.0
            matched: list[str] = []
            for pattern, weight in patterns:
                if pattern.search(query_lower):
                    theme_score += weight
                    matched.append(pattern.pattern)

            scores[theme] = theme_score
            matched_by_theme[theme] = matched

        # Find the best match
        best_theme = ResearchTheme.GENERAL
        best_score = 0.0

        for theme, score in scores.items():
            if score > best_score:
                best_score = score
                best_theme = theme

        # Normalize confidence to 0-1 range
        # Use a sigmoid-like normalization that caps at 1.0
        max_possible = self._get_max_possible_score(best_theme)
        if max_possible > 0:
            raw_confidence = best_score / max_possible
            # Apply a gentle curve to make mid-range scores more confident
            confidence = min(1.0, raw_confidence * 1.5)
        else:
            confidence = 0.0

        # If no patterns matched, default to GENERAL with low confidence
        if best_score == 0:
            best_theme = ResearchTheme.GENERAL
            confidence = 0.3  # Default confidence for unknown queries

        return DetectionResult(
            detected_theme=best_theme,
            confidence=confidence,
            matched_patterns=matched_by_theme.get(best_theme, []),
            all_scores={t.value: s for t, s in scores.items()},
        )

    def _get_max_possible_score(self, theme: ResearchTheme) -> float:
        """Get the maximum possible score for a theme.

        This is used to normalize confidence scores.
        """
        patterns = self.PATTERNS.get(theme, [])
        if not patterns:
            return 1.0
        # Use the sum of top 3 pattern weights as the "full confidence" threshold
        weights = sorted([w for _, w in patterns], reverse=True)
        return sum(weights[:3])

    def detect_with_fallback(
        self,
        query: str,
        explicit_theme: ResearchTheme | None = None,
    ) -> DetectionResult:
        """Detect theme with optional explicit override.

        Args:
            query: The research query to analyze.
            explicit_theme: Optional explicit theme to use (skips detection).

        Returns:
            DetectionResult with the theme to use.
        """
        if explicit_theme is not None:
            return DetectionResult(
                detected_theme=explicit_theme,
                confidence=1.0,
                matched_patterns=["explicit_selection"],
                all_scores={explicit_theme.value: 1.0},
            )

        result = self.detect(query)

        # If confidence is too low, fall back to GENERAL
        if not result.is_confident(self._confidence_threshold):
            return DetectionResult(
                detected_theme=ResearchTheme.GENERAL,
                confidence=0.5,
                matched_patterns=["fallback_to_general"],
                all_scores=result.all_scores,
            )

        return result

    def get_theme_hints(self, query: str) -> dict[str, Any]:
        """Get hints about which themes might be relevant.

        This is useful for debugging or displaying theme suggestions.

        Args:
            query: The research query to analyze.

        Returns:
            Dictionary with theme hints and matched patterns.
        """
        result = self.detect(query)
        return {
            "detected": result.detected_theme.value,
            "confidence": result.confidence,
            "matched_patterns": result.matched_patterns,
            "all_scores": result.all_scores,
        }


__all__ = ["ThemeDetector"]
