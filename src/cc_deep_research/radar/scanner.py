"""Source scanning for Radar.

This module provides:
- BaseScanner: abstract base for source scanners
- RSSScanner: scans RSS/Atom feeds (news, blog, changelog sources)
- SourceScanner: orchestrates scanning across all active sources
- Cadence parsing utilities
"""

from __future__ import annotations

import calendar
import hashlib
import logging
import re
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Any

import feedparser

from cc_deep_research.radar.models import (
    RadarSource,
    RawSignal,
    SourceStatus,
    SourceType,
)
from cc_deep_research.radar.storage import RadarStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class UnsupportedSourceTypeError(Exception):
    """Raised when a scanner cannot handle the given source type."""

    pass


class ScanError(Exception):
    """Raised when a scan fails for a source."""

    pass


# ---------------------------------------------------------------------------
# Cadence utilities
# ---------------------------------------------------------------------------

CAdENCE_MAP = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "2h": timedelta(hours=2),
    "6h": timedelta(hours=6),
    "12h": timedelta(hours=12),
    "1d": timedelta(days=1),
    "2d": timedelta(days=2),
    "7d": timedelta(days=7),
}


def parse_cadence(cadence_str: str) -> timedelta:
    """Parse a cadence string like '1h', '6h', '1d' into a timedelta.

    Args:
        cadence_str: A cadence string (e.g., "1h", "6h", "1d").

    Returns:
        Corresponding timedelta.

    Raises:
        ValueError: If the cadence string is not recognized.
    """
    if cadence_str in CAdENCE_MAP:
        return CAdENCE_MAP[cadence_str]
    raise ValueError(f"Unknown cadence: {cadence_str!r}")


def is_due_for_scan(source: RadarSource) -> bool:
    """Return True if a source is due for a scan based on its cadence.

    Args:
        source: The RadarSource to check.

    Returns:
        True if the source should be scanned now.
    """
    if source.status != SourceStatus.ACTIVE:
        return False

    if source.last_scanned_at is None:
        return True

    try:
        last_scanned = datetime.fromisoformat(source.last_scanned_at)
    except ValueError:
        return True

    # Ensure timezone-aware comparison
    if last_scanned.tzinfo is None:
        last_scanned = last_scanned.replace(tzinfo=UTC)

    cadence = parse_cadence(source.scan_cadence)
    return datetime.now(tz=UTC) - last_scanned >= cadence


# ---------------------------------------------------------------------------
# HTML stripping
# ---------------------------------------------------------------------------

_STRIP_HTML_RE = re.compile(r"<[^>]+>")


def strip_html(text: str | None) -> str:
    """Remove HTML tags from text.

    Args:
        text: Text that may contain HTML.

    Returns:
        Plain text with HTML tags removed.
    """
    if text is None:
        return ""
    text = _STRIP_HTML_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Content hashing
# ---------------------------------------------------------------------------


def compute_content_hash(title: str, url: str | None) -> str:
    """Compute a content hash for deduplication.

    Args:
        title: The signal title.
        url: The signal URL.

    Returns:
        SHA256 hash of title + url.
    """
    content = f"{title}|{url or ''}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Base scanner
# ---------------------------------------------------------------------------


class BaseScanner(ABC):
    """Abstract base for source scanners."""

    @staticmethod
    @abstractmethod
    def can_handle(source_type: SourceType) -> bool:
        """Return True if this scanner can handle the given source type."""
        ...

    @abstractmethod
    def scan(self, source: RadarSource, store: RadarStore) -> list[RawSignal]:
        """Fetch and normalize items from a source.

        Args:
            source: The RadarSource to scan.
            store: The RadarStore to use for any persistence during scan.

        Returns:
            List of normalized RawSignal records.

        Raises:
            ScanError: If the scan fails.
        """
        ...


# ---------------------------------------------------------------------------
# RSS Scanner
# ---------------------------------------------------------------------------

RSS_HANDLED_TYPES = {SourceType.NEWS, SourceType.BLOG, SourceType.CHANGELOG}


class RSSScanner(BaseScanner):
    """Scans RSS and Atom feeds."""

    # Timeout for HTTP requests in seconds
    FETCH_TIMEOUT = 30

    @staticmethod
    def can_handle(source_type: SourceType) -> bool:
        return source_type in RSS_HANDLED_TYPES

    def scan(self, source: RadarSource, store: RadarStore) -> list[RawSignal]:
        """Fetch an RSS/Atom feed and normalize entries into RawSignals.

        Args:
            source: The RadarSource with a feed URL.
            store: The RadarStore (used to update last_scanned_at).

        Returns:
            List of RawSignal records from the feed.

        Raises:
            ScanError: If the feed cannot be fetched or parsed.
        """
        url = source.url_or_identifier

        try:
            # feedparser handles If-Modified-Since, ETags, and HTTP caching
            feed = feedparser.parse(
                url,
                timeout=self.FETCH_TIMEOUT,
            )
        except Exception as exc:
            raise ScanError(f"Failed to fetch feed at {url}: {exc}") from exc

        if feed.bozo and feed.bozo_exception:
            # Log but don't fail - some feeds have minor XML issues
            logger.warning("Feed %s has minor issues: %s", url, feed.bozo_exception)

        signals: list[RawSignal] = []

        for entry in feed.entries:
            signal = self._normalize_entry(entry, source)
            if signal is not None:
                signals.append(signal)

        # Update last_scanned_at on the source
        self._update_last_scanned(source, store)

        return signals

    def _normalize_entry(
        self,
        entry: Any,
        source: RadarSource,
    ) -> RawSignal | None:
        """Normalize a feed entry into a RawSignal.

        Args:
            entry: A feedparser entry dict.
            source: The RadarSource this entry came from.

        Returns:
            A normalized RawSignal or None if the entry is invalid.
        """
        # Get title
        title = strip_html(getattr(entry, "title", None) or "")
        if not title:
            return None

        # Get summary/description
        summary = None
        for attr in ("summary", "description", "content"):
            raw_summary = getattr(entry, attr, None)
            if raw_summary:
                if isinstance(raw_summary, list):
                    raw_summary = raw_summary[0].get("value", "") if raw_summary else ""
                summary = strip_html(raw_summary)
                if summary:
                    summary = summary[:500]
                    break

        # Get URL
        url = None
        for attr in ("link", "id"):
            url = getattr(entry, attr, None)
            if url:
                break

        # Get external_id (GUID)
        external_id = getattr(entry, "id", None) or url

        # Get published_at
        published_at = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published_at = datetime.fromtimestamp(calendar.timegm(entry.published_parsed), tz=UTC)
                published_at = published_at.isoformat()
            except (ValueError, OSError):
                pass
        elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
            try:
                published_at = datetime.fromtimestamp(calendar.timegm(entry.updated_parsed), tz=UTC)
                published_at = published_at.isoformat()
            except (ValueError, OSError):
                pass

        # Compute content hash
        content_hash = compute_content_hash(title, url)

        # Determine normalized_type from source type
        normalized_type = source.source_type.value

        return RawSignal(
            source_id=source.id,
            external_id=external_id,
            title=title,
            summary=summary,
            url=url,
            published_at=published_at,
            content_hash=content_hash,
            normalized_type=normalized_type,
        )

    def _update_last_scanned(self, source: RadarSource, store: RadarStore) -> None:
        """Update the last_scanned_at timestamp on the source."""
        store.update_source(source.id, {"last_scanned_at": datetime.now(tz=UTC).isoformat()})


# ---------------------------------------------------------------------------
# Source Scanner orchestrator
# ---------------------------------------------------------------------------

_registered_scanners: list[type[BaseScanner]] = [RSSScanner]


def register_scanner(scanner_cls: type[BaseScanner]) -> None:
    """Register a scanner class to be used by SourceScanner.

    Args:
        scanner_cls: A BaseScanner subclass.
    """
    _registered_scanners.append(scanner_cls)


def _scanner_for(source_type: SourceType) -> BaseScanner:
    """Find the first registered scanner that can handle the source type.

    Args:
        source_type: The type of source to scan.

    Returns:
        A scanner instance that can handle the source.

    Raises:
        UnsupportedSourceTypeError: If no scanner can handle the source type.
    """
    for cls in _registered_scanners:
        if cls.can_handle(source_type):
            return cls()
    raise UnsupportedSourceTypeError(f"No scanner registered for source type: {source_type}")


class SourceScanner:
    """Orchestrates scanning across all active RadarSource records."""

    def __init__(self, store: RadarStore | None = None) -> None:
        """Initialize the scanner with an optional store.

        Args:
            store: RadarStore to use. Defaults to a new RadarStore.
        """
        self._store = store or RadarStore()

    def scan_source(self, source: RadarSource) -> list[RawSignal]:
        """Scan a single source and return normalized signals.

        Args:
            source: The RadarSource to scan.

        Returns:
            List of RawSignal records produced by the scan.
        """
        scanner = _scanner_for(source.source_type)
        try:
            return scanner.scan(source, self._store)
        except ScanError:
            # Mark source as errored
            self._store.update_source(source.id, {"status": SourceStatus.ERROR})
            return []

    def scan_due_sources(self) -> list[RawSignal]:
        """Scan all active sources that are due for scanning.

        Returns:
            Combined list of RawSignals from all scanned sources.
        """
        all_signals: list[RawSignal] = []
        sources = self._store.load_sources().sources

        for source in sources:
            if is_due_for_scan(source):
                signals = self.scan_source(source)
                all_signals.extend(signals)

        return all_signals

    def scan_all(self) -> list[RawSignal]:
        """Scan all active sources regardless of cadence.

        Returns:
            Combined list of RawSignals from all scanned sources.
        """
        all_signals: list[RawSignal] = []
        sources = self._store.load_sources().sources

        for source in sources:
            if source.status == SourceStatus.ACTIVE:
                signals = self.scan_source(source)
                all_signals.extend(signals)

        return all_signals
