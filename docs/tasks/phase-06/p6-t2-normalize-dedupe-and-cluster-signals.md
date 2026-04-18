# P6-T2: Normalize, Dedupe, and Cluster Signals

## Summary

Normalize fetched items into raw signals, deduplicate repeats, and cluster related signals into opportunities.

## Details

### What to implement

1. **Signal deduplication** - In `RadarStore`:
   - Check `content_hash` to skip signals already seen from the same source
   - Check `external_id` uniqueness within a source
   - `deduplicate_signals(new_signals: list[RawSignal]) -> list[RawSignal]` that returns only truly new signals

2. **Signal normalization** - In `RSSScanner`:
   - Normalize titles (strip HTML, trim whitespace)
   - Normalize summaries (strip HTML, truncate to 500 chars)
   - Compute `content_hash` from title + url for dedup
   - Extract `published_at` from feed entry

3. **Clustering logic** - `SignalClusterer` class:
   - Group signals by topic/entity using simple keyword extraction
   - Use title similarity (TF-IDF cosine similarity or simpler Jaccard on words)
   - Cluster signals that share significant keywords within a time window (e.g., 7 days)
   - Return a list of `SignalCluster` objects with grouped signal IDs

4. **Opportunity creation from clusters** - `OpportunityCreator`:
   - For each cluster, create one `Opportunity`
   - Use highest-scoring signal's title as opportunity title
   - Combine summaries from cluster signals
   - Detect `opportunity_type` based on source type and keywords
   - Link all signals to the opportunity via `OpportunitySignalLink`

5. **End-to-end ingest function** - `run_ingest_cycle()`:
   - Scan all due sources
   - Deduplicate incoming signals
   - Cluster signals into opportunities
   - Create/update opportunities in store

### Exit criteria

- Duplicate raw items do not create duplicate opportunities
- Signals from the same source with same content_hash are deduplicated
- Clusters are created with at least one signal
- Each opportunity has at least one linked signal
