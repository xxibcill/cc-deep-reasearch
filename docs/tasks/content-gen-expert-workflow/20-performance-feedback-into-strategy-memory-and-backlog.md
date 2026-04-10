# Task 20: Feed Performance Learning Back Into Strategy Memory And Backlog

Status: Done

Goal:
Turn post-publish performance analysis into durable learning that changes future strategy, backlog scoring, angle selection, and proof expectations instead of leaving performance insights isolated in a one-off report.

Primary files:
- `src/cc_deep_research/content_gen/models.py` - Added PerformanceLearning, PerformanceLearningSet, StrategyPerformanceGuidance, LearningDurability, LearningCategory
- `src/cc_deep_research/content_gen/agents/performance.py` - (existing, used by orchestrator)
- `src/cc_deep_research/content_gen/storage/performance_learning_store.py` - New store for performance learnings persistence
- `src/cc_deep_research/content_gen/storage/__init__.py` - Exports PerformanceLearningStore
- `src/cc_deep_research/content_gen/backlog_service.py` - (existing)
- `src/cc_deep_research/content_gen/orchestrator.py` - Updated to extract learnings after performance analysis
- `src/cc_deep_research/content_gen/prompts/backlog.py` - Updated score_ideas_user to include performance guidance

Scope:
- Define structured performance-learning outputs such as winning hooks, failed framings, audience-resonance notes, and updated proof heuristics.
- Add a controlled path for applying those learnings to strategy memory or backlog scoring inputs.
- Preserve operator visibility into which learnings are durable defaults versus one-run observations.
- Let future backlog or angle stages reference prior performance patterns when ranking ideas.

Implementation notes:
- Keep feedback loops explicit and reversible; strategy memory should not silently drift after every run.
- Favor additive stored guidance over mutating historical records in place.
- Separate platform-specific lessons from durable cross-platform strategy when possible.

Acceptance criteria:
- [x] Performance analysis can produce structured learnings that downstream planning stages can consume.
- [x] Strategy or backlog inputs can incorporate prior performance lessons without breaking existing manual workflows.
- [x] The stored feedback path is visible enough that operators can inspect or override it.

Validation:
- [x] Add tests for performance-learning model parsing and persistence behavior.
- [x] Add at least one orchestrator or backlog-scoring test showing performance learnings affecting future prioritization.

Out of scope:
- Automatic publishing decisions based on performance
- External analytics integrations beyond current inputs

## Implementation Summary

### New Models (models.py)
- `LearningDurability` enum: DURABLE, EXPERIMENTAL, REJECTED
- `LearningCategory` enum: HOOK, Framing, AUDIENCE, PROOF, FORMAT, PACING, CTA, PACKAGING, PLATFORM
- `PerformanceLearning`: Individual learning with observation, implication, guidance, durability, category, platform, timestamps
- `PerformanceLearningSet`: Container for learnings from a single analysis run
- `StrategyPerformanceGuidance`: Durable guidance stored in StrategyMemory (winning_hooks, failed_hooks, etc.)
- Added `performance_guidance` field to StrategyMemory

### New Store (performance_learning_store.py)
- `PerformanceLearningStore`: YAML persistence for learnings
- `extract_learnings_from_analysis()`: Converts PerformanceAnalysis to structured learnings
- `apply_learnings_to_strategy()`: Promotes learnings to durable strategy guidance (operator-gated)
- `get_active_learnings()`: Query learnings by category/durability/platform
- `get_durable_guidance_for_backlog()`: Returns scoring hints for backlog scoring

### Updated Prompts (backlog.py)
- `score_ideas_user()`: Now includes performance guidance from StrategyMemory in the scoring prompt

### Updated Orchestrator
- `run_performance()`: Now extracts and stores learnings after analysis
- `_stage_performance()`: Updated to extract learnings when ctx.performance is set

### Tests Added
- 14 new tests covering model serialization, store persistence, learning extraction, and prompt integration
