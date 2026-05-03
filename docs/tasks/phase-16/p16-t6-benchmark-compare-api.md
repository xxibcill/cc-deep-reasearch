# P16-T6: Add `/api/benchmarks/compare` Endpoint

## Summary

Add an endpoint to compare two benchmark runs, currently CLI-only.

## Details

- Add `POST /api/benchmarks/compare` or `GET /api/benchmarks/compare?dir1=X&dir2=Y` endpoint in `misc_routes.py`
  - Accept two run directory paths
  - Call `compare_benchmark_runs()` from `cc_deep_research.benchmark`
  - Return the `BenchmarkComparison` struct as JSON (metric deltas, case-level changes)
- Add compare UI in `dashboard/src/app/benchmark/compare/` page (or add to existing benchmark page)
  - Two-run selector dropdowns
  - Display deltas in a structured table

## Acceptance Criteria

- `POST /api/benchmarks/compare` returns comparison data for two runs
- Dashboard compare view shows metric deltas and case-level changes