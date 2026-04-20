# P9-T6: Extract or Remove AgentRegistry

## Summary

`AGENT_REGISTRY` in `agents/__init__.py` is defined but never called. Either integrate it for a plugin system or remove it.

## Details

### What to implement

1. **Audit `AGENT_REGISTRY` usage**:
   - Search for any code that calls `get_agent_class()` or iterates `AGENT_REGISTRY`
   - Check if it's used in any dynamic agent instantiation patterns
   - Check if it's intended for future plugin system

2. **Choose path**:

   **Option A - Integrate for plugin system** (if there's a real need):
   - Make `AgentRegistry` a proper plugin registry
   - Allow agents to be registered via entry points or config
   - Update `AgentAccess` to use the registry

   **Option B - Remove entirely** (if truly unused):
   - Delete `AGENT_REGISTRY` dict from `agents/__init__.py`
   - Delete `get_agent_class()` function
   - Delete any registry-related code in `AgentAccess`
   - Keep explicit imports instead

3. **Update imports**:
   - If removing, ensure all agent imports are explicit in `agents/__init__.py`
   - Update any dynamic lookup code to use direct instantiation

### Exit criteria

- `AGENT_REGISTRY` either removed or properly integrated
- No dead code remaining
- Agents instantiated directly or through intentional factory pattern
