# P8-T6 - Add Knowledge Benchmark Gates

## Functional Feature Outcome

The knowledge graph has regression gates that measure ingest quality, graph integrity, lint health, claim provenance, and whether knowledge-assisted planning improves research outcomes.

## Why This Task Exists

A cumulative knowledge graph can quietly rot if unsupported claims, duplicate pages, stale summaries, and contradictory synthesis are allowed to accumulate. This task makes the knowledge layer measurable before it becomes a core part of research planning.

## Scope

- Add benchmark fixtures for saved sessions with known claims, sources, gaps, and contradictions.
- Add graph integrity metrics:
  - node count by kind
  - edge count by kind
  - orphan page count
  - unsupported claim count
  - stale page count
  - duplicate node/page count
  - source-backed claim ratio
- Add benchmark comparison for runs with and without knowledge-assisted planning.
- Add CI-friendly lint thresholds.
- Document regression gates and expected manual review steps.

## Implementation Notes

- Keep live provider credentials out of benchmark tests.
- Use deterministic fixture sessions for ingest quality.
- Planning-impact benchmarks can use mocked provider responses at first.
- Treat graph growth as expected, but unsupported/stale/duplicate ratios should not regress silently.
- Store benchmark output in a format compatible with existing benchmark docs.

## Test Plan

- Fixture ingest benchmark with expected graph/page counts.
- Lint threshold tests for clean and intentionally broken vaults.
- Planning-impact tests using fixed local knowledge plus mocked retrieval.
- Export stability tests for graph JSON snapshots.
- Regression documentation check in `docs/REFACTOR_REGRESSION_CHECKLIST.md` or equivalent task docs.

## Acceptance Criteria

- Benchmark output reports graph integrity and lint health metrics.
- Source-backed claim ratio is measured and gated.
- Knowledge-assisted planning can be compared against baseline planning.
- CI can fail on broken graph invariants without requiring live web access.
- Regression instructions are documented.

## Verification Commands

```bash
uv run pytest tests/test_benchmark.py tests/test_operating_fitness.py -x
uv run pytest tests/test_session_store.py tests/test_research_run_service.py -x
uv run ruff check src/cc_deep_research/knowledge tests/
```

## Risks

- Benchmarks can become brittle if they overfit exact graph counts. Gate core ratios and invariants, not incidental ordering.
- Planning-impact scores may be noisy. Start with deterministic mocked retrieval before evaluating live runs.
