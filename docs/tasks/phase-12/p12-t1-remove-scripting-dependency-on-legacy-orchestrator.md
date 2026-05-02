# P12-T1 - Remove Scripting Dependency On Legacy Orchestrator

## Functional Feature Outcome

Standalone scripting continues to work, but it no longer relies on the deprecated legacy content-gen orchestrator.

## Why This Task Exists

`content_gen/orchestrator.py` exposes a deprecated compatibility shim, while `ScriptingApiService` still imports and instantiates `ContentGenOrchestrator`. That keeps `legacy_orchestrator.py` on the execution path even though the pipeline is the preferred content-gen runtime. Removing this dependency is the practical step needed before the legacy module can be reduced or deleted.

## Scope

- Trace the scripting behaviors that still require `ContentGenOrchestrator`.
- Move those behaviors to focused scripting or pipeline services.
- Preserve standalone script generation, iterative refinement, feedback, and context behavior.
- Keep the public scripting API stable.
- Add regression tests for the moved behavior.

## Current Friction

- `ScriptingApiService` has a default orchestrator factory that returns the deprecated orchestrator.
- Legacy orchestration code is much larger than the scripting behavior it is still needed for.
- Tests still import legacy behavior directly, which can make deletion paths unclear.

## Implementation Notes

- Start by preserving the `ScriptingApiService` public API and changing only its execution dependency.
- Keep any compatibility shim thin and explicitly marked as temporary.
- Avoid moving unrelated production, packaging, or publishing behavior in this task.
- Update tests to assert behavior through the supported scripting service path wherever possible.

## Test Plan

- Run existing standalone scripting tests before changing behavior.
- Add tests for script generation with stored context and generated context.
- Add tests for iterative feedback and refinement behavior.
- Add tests that prove the scripting service can run without constructing the deprecated orchestrator.

## Acceptance Criteria

- Normal scripting service execution does not instantiate `ContentGenOrchestrator`.
- Existing scripting API route behavior remains compatible.
- Iterative-loop tests pass through the supported service path.
- Remaining legacy orchestrator usage is documented and limited.

## Verification Commands

```bash
uv run pytest tests/test_content_gen_briefs.py tests/test_iterative_loop.py tests/test_content_gen_routes.py -x
uv run ruff check src/cc_deep_research/content_gen
```

## Risks

- The legacy orchestrator may contain implicit context defaults not documented elsewhere. Capture these in tests before moving behavior.
- Direct legacy tests may need to be rewritten around supported service behavior instead of deleted outright.
