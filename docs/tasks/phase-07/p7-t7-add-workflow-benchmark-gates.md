# P7-T7 - Add Workflow Benchmark Gates

## Functional Feature Outcome

Research workflow changes are evaluated through repeatable benchmark comparisons instead of subjective one-off runs.

## Why This Task Exists

The repo already has a benchmark corpus and deterministic scorecard metrics. Phase 07 upgrades core workflow behavior, retrieval, evidence handling, planner execution, and dashboard launch controls. Those changes need an explicit quality gate so staged remains stable and planner can be promoted based on evidence.

## Scope

- Extend the benchmark corpus with cases that stress planner, freshness, evidence quality, and report quality.
- Add benchmark configuration fields for workflow mode and provider mode.
- Compare staged and planner runs in one report.
- Add quality thresholds and regression warnings.
- Document required checks before marking Phase 07 complete.

## Current Friction

- The benchmark corpus covers useful baseline categories, but it does not explicitly compare staged versus planner workflow behavior.
- Scorecard metrics focus on source count, domain diversity, iteration count, latency, validation score, and stop reason.
- Report quality and evidence support are not first-class benchmark outputs yet.

## Benchmark Cases To Add

- `planner-multifacet-climate-risk`
  - Query: "Map the main climate risk disclosure requirements affecting multinational manufacturers in the U.S., EU, and Singapore."
  - Purpose: tests decomposition across jurisdictions and synthesis of separate regulatory threads.
- `freshness-us-ai-policy`
  - Query: "What are the latest U.S. federal AI safety and export-control policy changes affecting frontier model labs?"
  - Purpose: tests recency, explicit dates, and source freshness.
- `evidence-health-screen-time`
  - Query: "What does current evidence say about screen time limits and adolescent mental health outcomes?"
  - Purpose: tests nuanced evidence, uncertainty, and avoidance of overclaiming.
- `source-conflict-company-claims`
  - Query: "Compare company claims and independent analysis about direct air capture cost trends."
  - Purpose: tests source disagreement and conflict handling.
- `operator-actionable-market-entry`
  - Query: "Assess whether a B2B SaaS company should expand into Indonesia or Vietnam first, based on market, regulatory, and go-to-market factors."
  - Purpose: tests decision-oriented research and recommendations with limitations.

## Metrics To Add Or Preserve

- Existing:
  - source count
  - unique domains
  - source type diversity
  - iteration count
  - latency
  - validation score
  - stop reason
- Add:
  - workflow mode
  - provider mode
  - report quality score
  - unsupported claim count
  - citation error count
  - hydration success rate
  - freshness coverage for date-sensitive cases
  - planner subtask completion/failure counts

## Gate Policy

- Staged workflow is the baseline.
- Planner cannot become default unless:
  - average validation score is no worse than staged by an agreed threshold.
  - failed/degraded run count is no higher than staged.
  - unsupported claim count is not higher than staged.
  - date-sensitive cases include explicit current dates and freshness metadata.
  - latency is acceptable for the selected depth mode.
- Retrieval changes are acceptable only when source diversity, validation score, or evidence quality improves without introducing report-quality regressions.

## Implementation Notes

- Extend benchmark models without breaking old benchmark report loading.
- Add optional comparison mode:

```bash
cc-deep-research benchmark run --workflow staged --depth standard --output-dir benchmark_runs/staged
cc-deep-research benchmark run --workflow planner --depth standard --output-dir benchmark_runs/planner
cc-deep-research benchmark compare benchmark_runs/staged benchmark_runs/planner
```

- If a CLI command does not exist yet, add the minimal API needed to produce two reports and compare scorecards.
- Dashboard benchmark view should display workflow mode once the backend emits it.
- Store benchmark reports as diffable JSON.

## Test Plan

- Model tests for new benchmark fields with backward-compatible defaults.
- Corpus loading tests for new cases.
- Scorecard aggregation tests for new metrics.
- Comparison report tests for staged/planner deltas.
- Route tests if benchmark API payload changes.
- Dashboard type/build tests if benchmark UI changes.

## Acceptance Criteria

- Benchmark corpus includes planner, freshness, evidence-heavy, conflict, and decision-oriented cases.
- Benchmark reports include workflow mode and report/evidence quality metrics.
- Staged and planner runs can be compared in a deterministic report.
- Phase 07 exit criteria require benchmark results before planner is promoted beyond beta.
- Existing benchmark routes and dashboard benchmark page continue to load older reports.

## Verification Commands

```bash
uv run pytest tests/test_benchmark.py tests/test_web_server_misc_routes.py -x
uv run pytest tests/test_reporter.py tests/test_validator.py -x
cd dashboard && npm run build
```

Live/provider-backed verification when credentials are available:

```bash
cc-deep-research benchmark run --depth standard --workflow staged --output-dir benchmark_runs/phase-07-staged
cc-deep-research benchmark run --depth standard --workflow planner --output-dir benchmark_runs/phase-07-planner
```

## Risks

- Live benchmark outputs can vary because web search changes over time. Use deterministic scorecard thresholds and inspect diffs rather than requiring exact source equality.
- Adding too many metrics can make the benchmark hard to interpret. Keep the scorecard compact and put detailed evidence diagnostics in per-case reports.
