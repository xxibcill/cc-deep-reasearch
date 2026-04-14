# Phase 03 - Close The Learning Loop

## Functional Feature Outcome

Opportunity planning improves over time based on operator edits, downstream results, and post-publish outcomes instead of acting like a one-shot planning artifact.

## Why This Phase Exists

Even a high-quality brief is limited if the system never learns whether that brief led to strong ideas, better scripts, fewer QC issues, or better published performance. This phase turns opportunity planning into part of a feedback loop so future planning benefits from observed outcomes rather than only from manually entered strategy memory.

## Scope

- Compare opportunity-stage intent against later pipeline and publish outcomes.
- Add operator revision and versioning support for opportunity briefs.
- Feed reusable learnings back into future planning and strategy memory.

## Tasks

| Task | Summary |
| --- | --- |
| [P3-T1](./p3-t1-brief-vs-outcome-analysis.md) | Compare original opportunity assumptions against downstream and post-publish outcomes. |
| [P3-T2](./p3-t2-operator-revision-and-versioning.md) | Let operators review, revise, approve, and version opportunity briefs before deeper execution. |
| [P3-T3](./p3-t3-learning-store-and-planning-metrics.md) | Persist reusable patterns and track metrics that show whether opportunity planning quality is improving. |

## Dependencies

- Phase 01 contract hardening and Phase 02 traceability must be complete enough to make outcome comparisons trustworthy.
- Dashboard surfaces and some source of post-publish or operator-entered outcome data must exist for the learning loop to be meaningful.

## Exit Criteria

- The system can compare original brief intent against downstream and post-publish outcomes.
- Operators can revise and reuse opportunity briefs deliberately.
- Strategy or learning memory reflects validated planning lessons from prior runs.
- Opportunity-planning quality can be tracked over time with explicit metrics.
