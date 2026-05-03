# P16-T5: Add `/api/benchmarks/run` Endpoint for Dashboard

## Summary

Add an endpoint to trigger benchmark runs from the dashboard, currently only readable via `/api/benchmarks/runs`.

## Details

- Add `POST /api/benchmarks/run` endpoint in `misc_routes.py`
  - Accept `workflow_mode` (staged|planner), `depth` (quick|standard|deep), `output_dir` (optional)
  - Use `run_benchmark_corpus_sync()` with a `run_case` callback
  - The callback should use `ResearchRunService().run()` similarly to the CLI implementation
  - Return a run_id immediately and execute in background (or synchronous with timeout)
- Add "Run Benchmark" button/panel in `dashboard/src/app/benchmark/page.tsx`
  - Show workflow mode selector and depth selector
  - Display run progress and results

## Acceptance Criteria

- `POST /api/benchmarks/run` triggers a benchmark run and returns run results
- Dashboard benchmark page has UI to trigger runs
- Run results appear in run history and can be inspected