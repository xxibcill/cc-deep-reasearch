# Reusable Content Generation Workflow

This workflow describes a general content-production pipeline that turns a theme or business goal into a publish-ready content package. It does not assume a specific product, repository, or storage model, so it can be reused in other projects.

## Workflow Summary

| Stage | Input | Artifact Produced |
| --- | --- | --- |
| 1. Strategy setup | Brand goals, audience definition, channel constraints, tone rules, proof standards, past learnings | `Strategy` |
| 2. Opportunity planning | `Strategy`, campaign theme, market signal, operator brief | `OpportunityBrief` |
| 3. Backlog generation | `Strategy`, `OpportunityBrief` | `Backlog` |
| 4. Idea scoring and selection | `Backlog`, selection criteria, business priorities | `ScoringReport`, `Shortlist`, `SelectedIdea` |
| 5. Angle development | `SelectedIdea`, `Strategy`, audience priorities | `AngleOptions`, `SelectedAngle` |
| 6. Research assembly | `SelectedAngle`, source set, proof requirements | `ResearchPack` |
| 7. Argument design | `ResearchPack`, `SelectedAngle`, narrative goal | `ArgumentMap` |
| 8. Script development | `ArgumentMap`, `ResearchPack`, style constraints, platform constraints | `ScriptDraft`, `RevisedScript`, `ScriptPackage` |
| 9. Visual translation | `RevisedScript`, platform format, creative constraints | `VisualPlan` |
| 10. Production planning | `VisualPlan`, `RevisedScript`, available resources | `ProductionBrief` |
| 11. Packaging | `RevisedScript`, `SelectedAngle`, platform requirements | `PackagingSet` |
| 12. Quality control | `ScriptPackage`, `VisualPlan`, `ProductionBrief`, `PackagingSet`, fact rules | `QcReport`, `ApprovalDecision`, `FixList` |
| 13. Publish preparation | `ApprovalDecision`, `PackagingSet`, channel schedule | `PublishQueueItems`, `LaunchPlan` |
| 14. Performance review | Published content metrics, audience feedback, original plan | `PerformanceAnalysis`, `LearningNotes`, `NextTests` |

## Stage Notes

### 1. Strategy setup
- Input: core positioning, audience, platform mix, messaging boundaries, evidence standards, historical wins and failures.
- Output artifact: `Strategy`.

### 2. Opportunity planning
- Input: `Strategy` plus a campaign theme, trend, product priority, or editorial prompt.
- Output artifact: `OpportunityBrief` with target audience, problem framing, hypotheses, proof needs, and success criteria.

### 3. Backlog generation
- Input: `Strategy` and `OpportunityBrief`.
- Output artifact: `Backlog` of candidate content ideas, including rejected ideas or gaps if useful.

### 4. Idea scoring and selection
- Input: `Backlog` and a scoring rubric such as relevance, novelty, proof strength, effort, and expected impact.
- Output artifacts: `ScoringReport`, `Shortlist`, and `SelectedIdea`.

### 5. Angle development
- Input: `SelectedIdea`, audience needs, and messaging priorities.
- Output artifacts: `AngleOptions` and `SelectedAngle`.

### 6. Research assembly
- Input: `SelectedAngle`, source material, domain evidence, examples, and verification requirements.
- Output artifact: `ResearchPack` containing facts, examples, proof points, open questions, and claims needing validation.

### 7. Argument design
- Input: `ResearchPack`, `SelectedAngle`, and intended narrative arc.
- Output artifact: `ArgumentMap` with thesis, supporting claims, evidence anchors, objections, and beat structure.

### 8. Script development
- Input: `ArgumentMap`, `ResearchPack`, tone guidance, length targets, and platform constraints.
- Output artifacts: `ScriptDraft`, `RevisedScript`, and `ScriptPackage` with hooks, final copy, and supporting notes.

### 9. Visual translation
- Input: `RevisedScript` and the visual format required for the channel.
- Output artifact: `VisualPlan` that maps each beat to visuals, transitions, demonstrations, or on-screen text.

### 10. Production planning
- Input: `VisualPlan`, `RevisedScript`, and real production constraints such as people, props, locations, and tools.
- Output artifact: `ProductionBrief` with shoot setup, required assets, checks, pickup lines, and fallback plan.

### 11. Packaging
- Input: `RevisedScript`, `SelectedAngle`, and destination platform requirements.
- Output artifact: `PackagingSet` with captions, hooks, titles, keywords, hashtags, CTAs, thumbnails, or pinned-comment ideas.

### 12. Quality control
- Input: the full content package plus fact-checking and brand-safety rules.
- Output artifacts: `QcReport`, `ApprovalDecision`, and `FixList`.

### 13. Publish preparation
- Input: approved packaging and publishing constraints such as channel, schedule, and engagement plan.
- Output artifacts: `PublishQueueItems` and `LaunchPlan`.

### 14. Performance review
- Input: actual performance metrics, audience responses, and the original hypothesis or success criteria.
- Output artifacts: `PerformanceAnalysis`, `LearningNotes`, and `NextTests` that feed the next strategy cycle.

## Cross-Stage Supporting Artifacts

These artifacts are useful in most implementations even though they are not always user-facing:

- `StageTrace`: records stage status, timing, warnings, decisions, and short summaries for observability and debugging.
- `ClaimLedger`: tracks important claims back to evidence so review and fact-check steps stay auditable.
- `PipelineContext`: a single accumulated state object that stores the latest artifact from each stage and makes resume/review easier.

## Implementation Boundary

This workflow usually stops at planning, scripting, packaging, approval, scheduling, and learning. Actual filming, design production, rendering, or publishing can be handled by humans or external systems, using `VisualPlan`, `ProductionBrief`, and `PackagingSet` as the handoff artifacts.
