# P0-T2 - Record Quality Baseline

## Outcome

The project has a known quality baseline for tests, linting, type checks, and dashboard checks.

## Scope

- Run or document `uv run pytest`.
- Run or document `uv run ruff check src tests`.
- Run or document dashboard lint/build checks where dependencies are available.
- Record failures as pre-existing if they are unrelated to refactor edits.

## Implementation Notes

- If a check cannot run because dependencies or services are missing, document the blocker.
- Do not fix unrelated failures during this task.
- Capture command names and high-level failure summaries, not full noisy logs.

## Acceptance Criteria

- Each baseline check has a pass, fail, or blocked status.
- Known failures are clearly separated from future refactor regressions.

## Verification

- The baseline notes are sufficient for another engineer to reproduce the checks.

---

## Implementation Results

### Python Test Baseline
**Command**: `uv run pytest`
**Status**: ✅ PASS
**Summary**: 1067 passed, 8 warnings in 15.58s

**Warnings** (pre-existing, not related to refactor):
- Pydantic serializer warnings in `test_web_server.py` about `phase` field enum serialization
- Deprecation warning for `websockets.legacy` module

**Note**: Tests related to the dirty files (`test_web_server.py::test_content_gen_pipeline_websocket_streams_live_stage_events`, `test_content_gen_pipeline_websocket_streams_failed_stage_events`) pass as part of the 1067.

### Python Lint Baseline
**Command**: `uv run ruff check src tests`
**Status**: ❌ FAIL

**Failures**:
1. `src/cc_deep_research/content_gen/models/__init__.py:9` - I001 Import block is un-sorted or un-formatted
2. `src/cc_deep_research/content_gen/models/pipeline.py` - Multiple F821 (Undefined name) and UP037 (Remove quotes from type annotation) errors for:
   - `VisualProductionExecutionBrief`
   - `PackagingOutput`
   - `HumanQCGate`
   - `FactRiskGate`
   - `ProgressiveQCIssue`
   - `ProgressiveQCCheckpoint`
   - `EarlyPackagingSignals`

**Note**: These failures are **pre-existing** issues unrelated to refactor work. They appear to stem from the `models/` subpackage split (commit 43ccefb).

### Dashboard Lint Baseline
**Command**: `cd dashboard && npm run lint`
**Status**: ⚠️ PARTIAL (ESLint ran but reported "No files found")
**Details**: ESLint configured but no files matched the lint pattern. This may indicate the eslint config targets specific file extensions not currently present, or the check is set up for a different file structure.

### Dashboard Build
**Status**: ℹ️ NOT CHECKED (requires full `npm install && npm run dev` environment)

### Type Check Baseline
**Command**: `uv run mypy src --no-error-summary`
**Status**: ✅ PASS (no output indicates clean pass)

---

## Known Pre-existing Failures Summary

| Check | Status | Notes |
|-------|--------|-------|
| pytest | ✅ PASS | 1067 passed |
| ruff | ❌ FAIL | Import sorting + undefined names in models/ |
| mypy | ✅ PASS | Clean |
| dashboard lint | ⚠️ PARTIAL | ESLint config issue |
| dashboard build | ℹ️ NOT CHECKED | Requires full environment |

**Refactor regression = any NEW failure in ruff/mypy/pytest beyond these pre-existing failures.**
