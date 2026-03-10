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

## Next Tasks

(No pending tasks)
