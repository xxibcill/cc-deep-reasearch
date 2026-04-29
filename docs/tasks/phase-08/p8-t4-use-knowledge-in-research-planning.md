# P8-T4 - Use Knowledge In Research Planning

## Functional Feature Outcome

Research planning can optionally use prior local knowledge to reduce repeated discovery, target known gaps, reuse high-quality sources, and explain how prior knowledge influenced a run.

## Why This Task Exists

The graph only compounds if future research can consult it. This task wires prior knowledge into the planning and retrieval loop after post-run ingest is stable. The goal is not to replace web search; it is to make web search more deliberate by using known concepts, claims, contradictions, source quality, and unresolved gaps.

## Scope

- Add a knowledge retrieval service that reads `wiki/index.md`, page metadata, and graph records.
- Add config/request controls to enable or disable knowledge-assisted planning.
- Surface prior context in strategy analysis and query expansion.
- Seed follow-up queries from unresolved gaps and stale claims.
- Prefer known high-quality sources when they remain relevant.
- Record knowledge influence in `ResearchSession.metadata`.

## Implementation Notes

- Keep the default behavior conservative until benchmark results show benefit.
- Distinguish local prior knowledge from fresh web evidence in metadata and reports.
- Do not cite stale local claims as current evidence for time-sensitive queries without refresh.
- Query expansion should use prior gaps and contradictions as retrieval targets.
- Validation should be able to ask for refresh when local knowledge is old or weakly sourced.

## Test Plan

- Planning tests with a fixture graph showing added knowledge context.
- Query expansion tests for known gaps, contradictions, and stale claims.
- Session metadata contract tests for knowledge influence fields.
- Regression tests proving disabled knowledge mode behaves like the current workflow.
- Benchmark comparison across staged/planner runs with and without knowledge context.

## Acceptance Criteria

- Knowledge-assisted planning is optional and observable.
- Research runs record which prior pages/nodes influenced strategy or query expansion.
- Local knowledge can generate targeted follow-up queries for gaps and contradictions.
- Time-sensitive queries require freshness checks instead of blindly reusing old claims.
- Existing saved-session and dashboard contracts remain compatible.

## Verification Commands

```bash
uv run pytest tests/test_query_expander.py tests/test_orchestrator.py tests/test_research_run_service.py -x
uv run pytest tests/test_benchmark.py -x
uv run ruff check src/cc_deep_research/orchestration src/cc_deep_research/knowledge tests/
```

## Risks

- Feeding stale local knowledge into planning can reduce quality. Track freshness and source status explicitly.
- Overusing prior knowledge can create echo chambers. Validation should keep source diversity and contradiction pressure visible.
