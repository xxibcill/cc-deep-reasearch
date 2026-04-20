# P9-T1: Remove Dead Scaffolding

## Summary

Remove unused local scaffolding modules (`coordination/` and `teams/`) that create confusion and import overhead.

## Status

**Completed** - Both `coordination/` and `teams/` directories have been deleted.

## Details

### What to implement

1. **Audit `coordination/` module** - `LocalAgentPool`, `LocalMessageBus`, and `ResearchState` are documented as "local scaffolding only, not a distributed runtime." Verify no real usage:
   - Search for imports of `LocalAgentPool`, `LocalMessageBus` across the codebase
   - If truly unused, delete the entire `coordination/` directory

2. **Audit `teams/` module** - `LocalResearchTeam.execute_research()` raises `NotImplementedError`. Verify no real usage:
   - Search for imports of `LocalResearchTeam`
   - If truly unused, delete the entire `teams/` directory

3. **Update CLAUDE.md** - Remove references to dead scaffolding in the "Agent Naming vs Reality" table

4. **Update any docstrings** - Remove mentions of these modules from docstrings that reference them

### Exit criteria

- `coordination/` directory deleted or confirmed used
- `teams/` directory deleted or confirmed used
- CLAUDE.md updated if modules were deleted
- No broken imports after deletion
