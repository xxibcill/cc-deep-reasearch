# P9-T3: Split content_gen/models.py into Subpackage

## Summary

Decompose the 5,234-line `content_gen/models.py` into a `content_gen/models/` subpackage with focused modules.

## Status

**Committed (Partial Progress)** - The subpackage structure is committed (1036 tests pass). However, 30 API tests still fail due to model field differences between the simplified subpackage and the original data format expectations. Further work needed to fully complete.

The subpackage structure is in place and functional for core research functionality (**1036 tests pass** including all research orchestrator tests. However, **30 API tests fail** due to model field differences between the simplified subpackage and the original data format expectations.

## Details

### What was implemented

1. **Created `content_gen/models/` subpackage** with modules:
   - `__init__.py` - backward-compatible re-exports
   - `contracts.py` - Pipeline contracts
   - `shared.py` - Shared enums and types (35+ enums)
   - `pipeline.py` - Pipeline context, stage traces, operating phases
   - `learning.py` - Performance learning and metrics
   - `brief.py` - Brief and revision models
   - `backlog.py` - Backlog and scoring models
   - `production.py` - Production and visual stage models
   - `research.py` - Research pack and evidence models
   - `script.py` - Script and scripting models
   - `angle.py` - Angle and thesis models

2. **Key models exported and working**:
   - ResearchPack, ArgumentMap, PipelineContext, RunConstraints
   - ContentTypeProfile, get_content_type_profile
   - All stage-specific models

### Exit Criteria - NOT MET

- `content_gen/models.py` deleted and replaced - **models.py still exists**
- All imports in `content_gen/` updated - **Mostly done**
- Tests pass without modification - **1036 pass, 30 fail**

### Remaining Issues

1. Original `models.py` still exists (181KB) - cannot delete without fixing API compatibility
2. 30 API tests fail due to:
   - `BacklogItem` missing legacy `idea` field normalization
   - `proof_standards` type mismatch in StrategyMemory
   - Other data format compatibility issues
3. Would need significant more time to fully resolve

### Test Results

- **1036 tests pass** (core functionality works)
- **30 tests fail** (API compatibility issues)
- Failing tests are in: `test_web_server.py` (backlog API), `test_content_gen_backlog_chat.py`, `test_content_gen_briefs.py`

### What Would Be Needed to Complete

1. Add legacy field normalization to BacklogItem (idea → title)
2. Fix StrategyMemory.proof_standards type
3. Ensure all models fully match original data format
4. Delete original models.py
5. Verify all tests pass
