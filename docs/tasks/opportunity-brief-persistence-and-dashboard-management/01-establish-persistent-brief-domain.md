# Phase 01 - Establish Persistent Brief Domain

## Functional Feature Outcome

`OpportunityBrief` becomes a durable, version-aware resource with a clear lifecycle and storage boundary instead of existing only as transient pipeline state.

## Why This Phase Exists

Dashboard management is not credible until the brief has a canonical persisted shape and ownership model. The current code already treats the brief as important, but it is still mostly attached to a run. This phase separates the editorial artifact from one specific execution, defines which fields are mutable versus historical, and creates the persistence boundary that later API and UI work can safely build on.

## Scope

- Define the managed brief resource, lifecycle states, and immutable versus editable fields.
- Add a store and service abstraction for loading, saving, listing, and versioning briefs.
- Define migration and compatibility rules for existing generated briefs inside saved pipeline jobs.

## Tasks

| Task | Summary |
| --- | --- |
| [P1-T1](./p1-t1-brief-resource-model-and-lifecycle.md) | Define the canonical persisted brief resource model and lifecycle states. |
| [P1-T2](./p1-t2-brief-store-and-service.md) | Add a first-class brief store and service layer patterned after backlog persistence. |
| [P1-T3](./p1-t3-brief-version-history-and-migration-contract.md) | Define revision history and migration rules from existing pipeline-owned briefs. |

## Dependencies

- The current `OpportunityBrief` schema and pipeline usage must be understood well enough to avoid breaking downstream consumers.
- The implementation should preserve compatibility with saved `PipelineContext` payloads during rollout.

## Exit Criteria

- The codebase has a canonical persisted brief model that is not limited to `PipelineContext`.
- The system can save and reload briefs independently of a pipeline run.
- Version history and migration rules are explicit enough for later API and UI work.
