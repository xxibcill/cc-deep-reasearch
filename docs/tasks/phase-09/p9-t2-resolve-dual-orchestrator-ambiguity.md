# P9-T2: Resolve Dual Orchestrator Ambiguity

## Summary

Decide between `TeamResearchOrchestrator` and `PlannerResearchOrchestrator` — they have identical signatures but unclear hierarchy.

## Details

### What to implement

1. **Audit usage of both orchestrators**:
   - Search for imports and instantiations of both `TeamResearchOrchestrator` and `PlannerResearchOrchestrator`
   - Check if `PlannerResearchOrchestrator` is tested anywhere
   - Check if CLI or web server references one vs the other

2. **Make a decision**:
   - If `PlannerResearchOrchestrator` is unused/experimental → merge its logic into `TeamResearchOrchestrator` and delete it
   - If `PlannerResearchOrchestrator` is the intended replacement → make it the primary and deprecate `TeamResearchOrchestrator`
   - If both are needed for different modes → clearly document when to use which

3. **If deleting `PlannerResearchOrchestrator`**:
   - Remove `planner_orchestrator.py` from `orchestration/`
   - Update `orchestrator.py` exports
   - Update CLAUDE.md "Architecture" section

4. **If keeping both**:
   - Add docstrings clarifying the distinction
   - Add type hints so static checkers can catch misuse

### Exit criteria

- Only one authoritative orchestrator remains, or both have clear documented purposes
- No duplicate logic between orchestrators
- CLAUDE.md updated to reflect decision
