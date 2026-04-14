# Phase 02 - Expand Downstream Consumption

## Functional Feature Outcome

The opportunity brief becomes a real pipeline control surface whose fields explicitly shape backlog generation, idea scoring, research, QC, and later evaluation.

## Why This Phase Exists

The current stage produces useful planning information, but most of that information is not used strongly enough after the brief is created. That leaves the stage underpowered and makes several captured fields effectively decorative. This phase turns the brief into a first-class input to downstream decision-making and creates traceability from output artifacts back to the original planning intent.

## Scope

- Make more downstream stages consume `OpportunityBrief` explicitly.
- Add traceability from backlog and scoring outputs back to brief fields.
- Use `research_hypotheses` and `success_criteria` in later research and evaluation stages.

## Tasks

| Task | Summary |
| --- | --- |
| [P2-T1](./p2-t1-backlog-and-scoring-traceability.md) | Map generated and shortlisted ideas back to audience, problem, sub-angle, and proof constraints from the brief. |
| [P2-T2](./p2-t2-research-hypothesis-integration.md) | Feed opportunity-stage hypotheses into research-pack generation so evidence gathering tests the planned claims. |
| [P2-T3](./p2-t3-success-criteria-in-qc-and-performance.md) | Use brief-defined success criteria in QC and post-publish evaluation flows. |

## Dependencies

- Phase 01 contract hardening must make the brief stable enough to trust as a downstream input.
- Backlog, scoring, research-pack, QC, and performance prompt contracts must be updated carefully to preserve parser compatibility.

## Exit Criteria

- Backlog and scoring outputs can explain how they satisfy the opportunity brief.
- Research-pack generation uses opportunity-stage hypotheses directly.
- QC and performance analysis can reference the original success criteria.
- Major downstream decisions can be traced back to the brief instead of only the raw theme.
