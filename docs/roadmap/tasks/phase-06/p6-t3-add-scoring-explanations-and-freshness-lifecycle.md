# P6-T3 - Add Scoring, Explanations, And Freshness Lifecycle

## Status

Proposed.

## Summary

Rank Radar opportunities using explainable score components and manage how opportunities rise or decay over time.

## Scope

- Add scoring components and total score calculation.
- Add priority labels.
- Generate a human-readable "why this matters" explanation.
- Add freshness decay and rescore behavior.

## Out Of Scope

- User feedback learning loops
- Downstream workflow conversion

## Read These Files First

- `docs/opportunity-radar-prd.md`
- `src/cc_deep_research/radar/models.py`
- `src/cc_deep_research/radar/engine.py`
- `src/cc_deep_research/content_gen/storage/strategy_store.py`

## Suggested Files To Create Or Change

- `src/cc_deep_research/radar/scoring.py`
- `src/cc_deep_research/radar/engine.py`
- `tests/test_radar_scoring.py`

## Implementation Guide

1. Start with deterministic score components from the PRD:
   - strategic relevance
   - novelty
   - urgency/freshness
   - evidence strength
   - business value
   - workflow fit
2. Keep the first implementation simple and inspectable. Save the component breakdown on every scored opportunity.
3. Add a helper that maps numeric scores into labels like `Act Now`, `High Potential`, `Monitor`, and `Low Priority`.
4. Generate explanation text from score components and source evidence. Use templated text first if that is easier to test than LLM output.
5. Add freshness decay rules so stale opportunities naturally drop unless meaningful new evidence arrives.
6. Add tests for:
   - high-relevance opportunities outrank weak ones
   - stale items decay
   - new evidence can raise an old opportunity again

## Guardrails For A Small Agent

- Do not hide the scoring math. Persist the breakdown.
- Do not require an LLM for core ranking correctness.
- Do not let opportunities stay permanently high-priority with no new evidence.

## Deliverables

- Scoring module
- Explanation generation
- Freshness lifecycle logic
- Scoring tests

## Dependencies

- P6-T2 normalization and opportunity engine

## Verification

- Run `uv run pytest tests/test_radar_scoring.py tests/test_radar_engine.py -v`
- Inspect stored score breakdowns and explanations manually for one fixture

## Acceptance Criteria

- Opportunities have score breakdowns, labels, and explanations.
- Freshness decay works deterministically.
- Ranking is inspectable enough for frontend and telemetry consumers to trust.
