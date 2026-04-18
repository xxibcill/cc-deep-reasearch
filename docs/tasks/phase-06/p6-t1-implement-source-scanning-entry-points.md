# P6-T1: Implement Source Scanning Entry Points

## Summary

Implement source configuration rules and scanning entry points for the first supported source types (RSS/Atom feeds for news and blogs).

## Details

### What to implement

1. **SourceConfig rules** - A configuration model that defines how to scan each source type:
   - `RSSFeedConfig` for news/blog/changelog sources
   - Configurable fetch cadence per source

2. **Scanner base class** - `BaseScanner` abstract class with:
   - `can_handle(source_type)` check
   - `scan(source: RadarSource) -> list[RawSignal]` method
   - Error handling and status update on the source

3. **RSSScanner implementation** - Handles `news`, `blog`, `changelog` source types:
   - Fetches RSS/Atom feeds using `feedparser`
   - Normalizes items into `RawSignal` records
   - Maps feed entries to signal fields (title, summary, url, published_at)
   - Detects duplicates using `external_id` (item GUID)

4. **Source scanning service** - `SourceScanner` class that:
   - Loads active sources from store
   - Routes each to the appropriate scanner
   - Handles scan errors gracefully without crashing
   - Updates `last_scanned_at` on the source

5. **Cron/interval helpers** - Functions to parse cadence strings ("1h", "6h", "1d") and determine if a source is due for scanning.

### Exit criteria

- `SourceScanner.scan_all()` produces `RawSignal` records for configured RSS sources
- Unknown source types raise `UnsupportedSourceTypeError`
- Scanner errors are caught and logged without crashing the scan loop
- `last_scanned_at` is updated after each scan
