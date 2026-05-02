# Phase 12 - Legacy Content-Gen Orchestrator Retirement

## Functional Feature Outcome

Standalone and iterative scripting flows run through focused content-gen services instead of keeping the deprecated legacy orchestrator as a required execution dependency.

## Why This Phase Exists

The project already marks `ContentGenOrchestrator` as deprecated in favor of `ContentGenPipeline`, but the legacy orchestrator still remains large and active because standalone scripting depends on it. This keeps old orchestration code on the critical path and makes later content-gen changes more expensive. This phase extracts the remaining useful standalone scripting behavior so the compatibility shim can shrink or eventually be removed.

## Scope

- Identify the standalone scripting and iterative-loop behavior still served by the legacy orchestrator.
- Move that behavior behind focused content-gen services that do not require the legacy orchestrator.
- Preserve public scripting API behavior and existing iterative-loop semantics.
- Reduce the legacy orchestrator to a compatibility shim where practical.

## Tasks

| Task | Summary |
| --- | --- |
| [P12-T1](../tasks/phase-12/p12-t1-remove-scripting-dependency-on-legacy-orchestrator.md) | Move standalone scripting behavior off the deprecated content-gen orchestrator while preserving compatibility tests. |

## Dependencies

- Phase 09 should consolidate shared lane behavior first, so legacy code does not own unique lane rules.
- Phase 10 should stabilize the pipeline lifecycle before scripting behavior is moved onto the newer path.
- Existing standalone scripting and iterative-loop tests should define the compatibility baseline.

## Exit Criteria

- `ScriptingApiService` no longer needs to instantiate the deprecated `ContentGenOrchestrator` for normal execution.
- Existing standalone scripting and iterative-loop tests pass.
- The legacy orchestrator has a smaller compatibility role or a documented deletion path.
- No public scripting route behavior changes are required.
