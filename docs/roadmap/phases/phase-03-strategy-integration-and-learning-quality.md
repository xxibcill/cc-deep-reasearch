# Phase 03 - Strategy Integration And Learning Quality

## Functional Feature Outcome

The upgraded strategy model meaningfully influences planning, scoring, scripting, packaging, and learning promotion, while performance learnings become structured enough to reuse safely.

## Why This Phase Exists

A richer schema and better editor only matter if the pipeline actually uses the data. Right now some strategy fields influence prompts, but many do not, and the learning system still promotes vague summaries that are too weak to become durable rules. This phase makes strategy operational by wiring it into generation decisions and improving the quality of the learning layer.

## Scope

- Update planning, backlog, scoring, thesis, angle, packaging, and execution prompts to use the upgraded strategy fields.
- Route platform, pillar, proof, and CTA guidance into relevant downstream stages.
- Replace vague promoted learnings with structured rule-like records containing evidence, context, and confidence.
- Keep compatibility with the existing `performance_guidance` block while making richer learning objects the source of truth.

## Tasks

| Task | Summary |
| --- | --- |
| [P3-T1](../tasks/phase-03/p3-t1-wire-strategy-into-pipeline-stages.md) | Integrate upgraded strategy fields into prompts, agents, and orchestrator decisions. |
| [P3-T2](../tasks/phase-03/p3-t2-upgrade-learning-payloads.md) | Upgrade learnings to capture exact pattern, context, evidence, confidence, and review timing. |
| [P3-T3](../tasks/phase-03/p3-t3-derive-durable-guidance-from-structured-learnings.md) | Promote structured learnings into durable guidance without losing backward compatibility. |

## Dependencies

- Phase 01 must define the stable schema.
- Phase 02 should expose the strategy fields operators need to populate before this phase can deliver full value.

## Exit Criteria

- The major content-generation stages use upgraded strategy fields in their prompt/context construction.
- Promoted learnings include enough context to justify reuse and review.
- Durable guidance is traceable back to source learnings and source content IDs.
- Strategy has visible steering power over generation and scoring outcomes.
