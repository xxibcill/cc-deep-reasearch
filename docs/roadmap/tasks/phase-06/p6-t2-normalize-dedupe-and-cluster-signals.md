# P6-T2 - Normalize, Dedupe, And Cluster Signals

## Status

Proposed.

## Summary

Turn fetched scan results into raw signals, deduplicate repeated inputs, and cluster related signals into candidate opportunities.

## Scope

- Normalize different scan outputs into one raw signal shape.
- Deduplicate repeated items by stable fingerprint or content hash.
- Group related signals into opportunity candidates.
- Upsert opportunities instead of blindly creating duplicates.

## Out Of Scope

- Final ranking calibration
- Dashboard rendering

## Read These Files First

- `src/cc_deep_research/radar/models.py`
- `src/cc_deep_research/radar/stores.py`
- `src/cc_deep_research/radar/service.py`

## Suggested Files To Create Or Change

- `src/cc_deep_research/radar/normalization.py`
- `src/cc_deep_research/radar/engine.py`
- `tests/test_radar_normalization.py`
- `tests/test_radar_engine.py`

## Implementation Guide

1. Define a single normalization function that turns each scanner output into a `RawSignal`.
2. Use stable hashes or source-native ids to deduplicate raw items before persisting them.
3. After signals are saved, group them into opportunities using simple, explainable heuristics.
4. Keep clustering logic intentionally conservative. It is better to under-cluster than to merge unrelated opportunities.
5. Add explicit link records between opportunities and raw signals.
6. Make opportunity upsert rules deterministic. Suggested approach:
   - if a candidate matches an existing opportunity fingerprint or title/topic cluster, update it
   - otherwise create a new opportunity

## Guardrails For A Small Agent

- Do not rely on vague LLM matching for the first pass if deterministic rules can do the job.
- Do not skip provenance links between signals and opportunities.
- Do not create a new opportunity record if the change is only a duplicate signal.

## Deliverables

- Raw signal normalization layer
- Signal deduplication logic
- Opportunity clustering/upsert logic
- Engine tests for duplicate and non-duplicate cases

## Dependencies

- P6-T1 scanning entry points

## Verification

- Run `uv run pytest tests/test_radar_normalization.py tests/test_radar_engine.py -v`
- Confirm duplicate scan items do not create duplicate signals or opportunities

## Acceptance Criteria

- Multiple raw scan results can become a coherent opportunity candidate.
- Raw signals remain traceable after clustering.
- Duplicate inputs are suppressed predictably.
