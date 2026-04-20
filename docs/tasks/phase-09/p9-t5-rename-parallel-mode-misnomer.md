# P9-T5: Rename parallel_mode Misnomer

## Summary

Rename `parallel_mode` / `num_researchers` to `concurrent_source_collection` to match the actual behavior (concurrent asyncio, not distributed agents).

## Details

### What to implement

1. **Audit current `parallel_mode` usage**:
   - Find all references to `parallel_mode` and `num_researchers` parameters
   - Identify where `LocalAgentPool` is created or referenced

2. **Rename parameters and variables**:
   - `parallel_mode` → `concurrent_source_collection` (bool)
   - `num_researchers` → `max_concurrent_sources` (int)
   - Update all call sites

3. **Remove `LocalAgentPool` abstraction**:
   - `LocalAgentPool` is only used for this misnamed feature
   - After renaming, the actual implementation is just asyncio task management
   - Consider removing `LocalAgentPool` entirely if it's just tracking state

4. **Update CLI and config**:
   - Update CLI argument names
   - Update config schema if these are config options
   - Update CLAUDE.md "Agent Naming vs Reality" table

5. **Update docstrings**:
   - Clarify that this is concurrent asyncio execution, not distributed agents

### Exit criteria

- No references to `parallel_mode` or `num_researchers` remain
- `LocalAgentPool` removed or clearly documented as purely local
- CLAUDE.md updated
