# Opportunity Planning Improvement Task Pack

## Goal

Improve the `plan_opportunity` stage so it becomes a reliable, high-signal editorial planning step that materially shapes downstream backlog, research, scoring, and evaluation.

## Current State

The current opportunity-planning stage is useful but narrow.

- It converts a raw `theme` and `StrategyMemory` into an `OpportunityBrief`.
- It depends on a fragile text-output contract with exact headers.
- It fails fast when a few core fields are missing.
- It mostly influences backlog generation, while several output fields are only stored or displayed and do not strongly affect downstream execution.

Relevant implementation:

- `src/cc_deep_research/content_gen/agents/opportunity.py`
- `src/cc_deep_research/content_gen/prompts/opportunity.py`
- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/prompts/backlog.py`
- `dashboard/src/components/content-gen/stage-panels/plan-opportunity-panel.tsx`

## Product Intent

Opportunity planning should not just be a formatting step between strategy load and backlog generation.

It should act as the editorial control point for the content pipeline:

- refining a vague theme into a concrete opportunity
- defining who the content is for and what problem it addresses
- setting proof and platform constraints
- generating hypotheses and success criteria that later stages can actually use
- producing signals that help operators trust or reject the brief before more pipeline cost is incurred

## Recommended Rollout

Use a 3-phase plan:

1. Stabilize the stage contract and validation behavior.
2. Make the opportunity brief drive more of the pipeline.
3. Close the learning loop so opportunity planning improves with usage and outcomes.

## Non-Goals

Do not combine this task pack with broader prompt-platform refactors unless the opportunity stage is the direct beneficiary.

Do not redesign the entire content-generation pipeline around this change in the first implementation slice.

Do not add speculative product complexity before the brief is reliably structured and consumed.

## Task Files

- `01-stabilize-contract-and-validation.md`
- `02-expand-downstream-consumption.md`
- `03-close-the-learning-loop.md`
- `p1-t1-structured-output-contract.md`
- `p1-t2-semantic-validation-and-quality-signals.md`
- `p1-t3-model-contract-alignment.md`
- `p2-t1-backlog-and-scoring-traceability.md`
- `p2-t2-research-hypothesis-integration.md`
- `p2-t3-success-criteria-in-qc-and-performance.md`
- `p3-t1-brief-vs-outcome-analysis.md`
- `p3-t2-operator-revision-and-versioning.md`
- `p3-t3-learning-store-and-planning-metrics.md`

## Advice For The Implementer

- Fix the contract first. The current stage is too parser-coupled to safely expand downstream reliance without hardening it.
- Bias toward explicit validation and traceability over tolerant-but-vague outputs.
- Do not add new `OpportunityBrief` fields without also defining who consumes them.
- Treat operator visibility as part of the feature, not an afterthought. Weak opportunity briefs should be easy to detect in the dashboard and traces.
