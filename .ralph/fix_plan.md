# Fix Plan

## Completed Tasks

### 2026-03-10: Fix --show-timeline option not working without --monitor

**Issue:** The `--show-timeline` option did not display the timeline unless `--monitor` was also passed because the ResearchMonitor needed to be enabled to collect events.

**Fix:**
1. Modified `cli.py` line 139 to enable the monitor when `--show-timeline` is passed:
   ```python
   research_monitor = ResearchMonitor(enabled=(monitor or show_timeline) and not quiet)
   ```

2. Modified `monitoring.py` `log_researcher_event()` method to create `MonitorEvent` objects that get added to `self._events`, which `show_timeline()` uses to display the timeline.

**Files Modified:**
- `src/cc_deep_research/cli.py`
- `src/cc_deep_research/monitoring.py`

**Verification:** Ran `uv run cc-deep-research research --parallel-mode --num-researchers 4 --show-timeline "Health Benefit of White tea" --output whitetea.md` successfully. The timeline now displays at the end of the research.

### 2026-03-10: Fix failing tests

**Issue:** Several tests were failing due to outdated expectations and missing parameters:

1. `test_extract_themes_uses_claude_cli` - Expected `--tools ''` in CLI command but implementation no longer includes it
2. `test_api_mode_requires_claude_cli` - Failed because `CLAUDECODE` env var was set, causing early return
3. `test_execute_runs_flow_and_finalizes_session` and `test_execute_always_calls_shutdown` - Missing `config` parameter in `ResearchExecutionService` constructor
4. `test_execute_research_contract_by_depth[deep]` - `FakeDeepAnalyzerAgent.deep_analyze()` returned `AnalysisResult` instead of `dict`

**Fix:**
1. Updated `test_llm_analysis_client.py` to remove `--tools ''` from expected command
2. Added `monkeypatch.delenv("CLAUDECODE", raising=False)` to unset the env var in `test_api_mode_requires_claude_cli`
3. Added `Config` import and `config=config` parameter to both `ResearchExecutionService` tests in `test_orchestration.py`
4. Changed `FakeDeepAnalyzerAgent.deep_analyze()` to return a dict matching the real `DeepAnalyzerAgent.deep_analyze()` return type

**Files Modified:**
- `tests/test_llm_analysis_client.py`
- `tests/test_orchestration.py`
- `tests/test_orchestrator.py`

**Verification:** All 261 tests pass (1 skipped).

## Next Tasks

(No pending tasks)
