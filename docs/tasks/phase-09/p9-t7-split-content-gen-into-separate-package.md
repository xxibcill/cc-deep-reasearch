# P9-T7: Consider Splitting content_gen into Separate Package

## Summary

Evaluate whether `content_gen/` should become a separate top-level package (`cc_content_gen/`) co-located in the same repository.

## Details

### What to do

This is a **decision task**, not an implementation task. Investigate and document:

1. **Analyze shared dependencies**:
   - What does `content_gen/` actually share with `cc_deep_research/`?
   - Config schema? LLM routing? Telemetry stores?
   - Are there actual shared utilities or just coincidental proximity?

2. **Analyze coupling**:
   - Can `content_gen/` run independently?
   - Does it import from `cc_deep_research/` directly?
   - Are there circular dependencies?

3. **Evaluate pros/cons of splitting**:

   **Pros:**
   - Clearer product boundaries
   - Independent versioning/deployment
   - Smaller per-package cognitive load
   - `cc_deep_research/` becomes ~30% smaller

   **Cons:**
   - Duplicate config/llm/telemetry code if not shared
   - More complex CI/CD
   - harder to share utilities
   - Repository becomes multi-package

4. **Document decision**:
   - If splitting: Create phase-10 with the migration plan
   - If keeping: Document why in CLAUDE.md and close this as "not doing"

### Exit criteria

- Decision documented in CLAUDE.md
- If splitting: Phase-10 created with migration tasks
- If keeping: `content_gen/` co-location rationale documented
