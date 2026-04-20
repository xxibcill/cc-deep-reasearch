# Phase 09 - Refactor Massive Enormous Project

## Functional Feature Outcome

The codebase is cleaner, more navigable, and free of dead scaffolding. Monolithic files are decomposed into focused modules. Misnamed concepts are corrected.

## Why This Phase Exists

This project has grown to ~384K lines across 186 Python files with two distinct workflows (research + content generation) co-located in one package. Several architectural issues have accumulated: dead scaffolding that creates confusion, monolithic files that violate single responsibility, dual orchestrators with unclear hierarchy, and misnamed concepts that misdirect readers. This phase addresses the highest-impact structural issues.

## Scope

- Remove dead scaffolding (`coordination/`, `teams/`)
- Resolve dual orchestrator ambiguity
- Split `content_gen/models.py` (5,234 lines) into subpackage
- Split `content_gen/orchestrator.py` (4,302 lines) into per-stage orchestrators
- Rename `parallel_mode` misnomer
- Extract or remove `AgentRegistry`
- Evaluate splitting `content_gen/` into separate package

## Tasks

| Task | Summary |
| --- | --- |
| [P9-T1](../tasks/phase-09/p9-t1-remove-dead-scaffolding.md) | Remove unused `coordination/` and `teams/` modules |
| [P9-T2](../tasks/phase-09/p9-t2-resolve-dual-orchestrator-ambiguity.md) | Decide between `TeamResearchOrchestrator` and `PlannerResearchOrchestrator` |
| [P9-T3](../tasks/phase-09/p9-t3-split-content-gen-models.md) | Decompose `content_gen/models.py` into `content_gen/models/` subpackage |
| [P9-T4](../tasks/phase-09/p9-t4-split-content-gen-orchestrator.md) | Decompose `content_gen/orchestrator.py` into per-stage orchestrators |
| [P9-T5](../tasks/phase-09/p9-t5-rename-parallel-mode-misnomer.md) | Rename `parallel_mode` to `concurrent_source_collection` |
| [P9-T6](../tasks/phase-09/p9-t6-extract-or-remove-agent-registry.md) | Integrate or remove unused `AGENT_REGISTRY` |
| [P9-T7](../tasks/phase-09/p9-t7-split-content-gen-into-separate-package.md) | Evaluate splitting `content_gen/` into separate package |

## Dependencies

- All tasks are independent and can be executed in any order
- P9-T7 (split evaluation) should inform whether P9-T3 and P9-T4 do minimal or maximal decomposition

## Exit Criteria

- Dead scaffolding removed and CLAUDE.md updated
- Single authoritative orchestrator with clear purpose
- `content_gen/models.py` replaced with subpackage
- `content_gen/orchestrator.py` replaced with per-stage orchestrators
- No `parallel_mode` / `num_researchers` misnomers remain
- `AGENT_REGISTRY` either removed or properly integrated
- Decision on `content_gen/` split documented
