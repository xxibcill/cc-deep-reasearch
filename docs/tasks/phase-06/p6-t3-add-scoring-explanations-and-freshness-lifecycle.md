# P6-T3: Add Scoring Explanations and Freshness Lifecycle

## Summary

Add scoring, priority labels, ranking explanations, freshness decay, and engine-level tests.

## Details

### What to implement

1. **Scoring explanations** - In `RadarService.save_score()`:
   - Generate human-readable `explanation` string
   - Explain each dimension: "Strategic fit is high because X", "Novelty is medium because Y"
   - Mention which signals contributed to the score

2. **Signal-based scoring** - `ScoreCalculator` class:
   - Score `strategic_relevance` based on keyword matching against configurable strategy keywords
   - Score `novelty` based on how old the newest signal in the cluster is (newer = higher)
   - Score `urgency` based on recency of publication and source type (news > blog)
   - Score `evidence` based on number of signals in cluster (more signals = higher evidence)
   - Score `business_value` based on opportunity type (competitor_move > rising_topic)
   - Score `workflow_fit` based on how actionable the opportunity is right now

3. **Freshness decay** - `FreshnessManager` class:
   - `compute_freshness_state(opportunity: Opportunity, signals: list[RawSignal]) -> FreshnessState`
   - `FRESH`: newest signal within 24h
   - `STALE`: newest signal between 24h and 72h
   - `EXPIRED`: newest signal older than 72h
   - `NEW`: opportunity created within last 6h
   - Apply freshness decay on opportunity update

4. **Rescore trigger** - When new signals are added to an existing opportunity:
   - Trigger a rescore of the opportunity
   - Update `freshness_state` accordingly
   - Regenerate explanation

5. **Engine-level tests** - In `tests/test_radar_engine.py`:
   - Test end-to-end ingest cycle
   - Test deduplication logic
   - Test clustering
   - Test scoring with explanations
   - Test freshness state transitions
   - Test that duplicate signals don't create duplicate opportunities

### Exit criteria

- Opportunities contain score details and human-readable explanations
- Freshness state transitions are covered by tests
- Rescore behavior is triggered when new signals arrive
- All engine-level tests pass
