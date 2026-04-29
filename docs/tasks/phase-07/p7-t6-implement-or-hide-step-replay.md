# P7-T6 - Implement Or Hide Step Replay

## Functional Feature Outcome

Replayable checkpoint behavior becomes honest: operators can either rerun supported workflow steps, or the product stops presenting replay as an available action.

## Why This Task Exists

The session routes include a rerun-step endpoint that can detect replayable checkpoints, but it currently returns `501` because execution is not implemented. That is acceptable as an API placeholder, but it is not a finished operator workflow. This task resolves the mismatch by either implementing a narrow replay path or hiding the affordance until replay is ready.

## Scope

- Audit all UI/API references to rerun-step behavior.
- Decide whether Phase 07 implements narrow replay or hides it.
- If implementing, support replay for a conservative first set of phase checkpoints.
- If hiding, remove or disable dashboard actions that imply rerun is available.
- Preserve API honesty: unsupported replay must return a clear non-success response.

## Current Friction

- `/api/sessions/{session_id}/rerun-step` returns `501` for replayable checkpoints with a message that execution is not implemented yet.
- Checkpoint models include replayable metadata, but there is no execution service that can rebuild enough runtime state to rerun a phase safely.
- Replaying one phase can invalidate downstream artifacts, reports, and telemetry unless lineage is handled explicitly.

## Option A: Implement Narrow Replay

Start with only the safest replay targets:

- `source_collection` from a saved query family input.
- `analysis` from saved source input.
- `report` from saved session and analysis metadata.

Required behavior:

- Create a new derived session or artifact rather than mutating the original silently.
- Record parent session id and checkpoint id.
- Mark downstream outputs as regenerated.
- Emit telemetry for replay start/completion/failure.
- Reject replay when the checkpoint lacks enough `input_ref` data.
- Reject replay for planner beta steps until planner checkpoint state is complete.

## Option B: Hide Until Ready

If replay implementation is too broad for this phase:

- Keep API returning `501` for replayable checkpoints.
- Hide rerun buttons/actions in dashboard surfaces.
- Update docs to say checkpoint replay metadata exists for future use but execution is not available.
- Keep tests that assert the API does not claim success.

## Recommended Path

Use Option B unless there is a concrete operator need for replay in this release. If implementing, start with report-only replay because it has the lowest external side effects and can reuse saved session data.

## Test Plan

- If hiding:
  - Dashboard e2e verifies no rerun action is shown.
  - API route tests continue to assert `501` for replayable checkpoints.
  - Docs mention replay is not operational yet.
- If implementing:
  - Replay rejects missing checkpoint.
  - Replay rejects non-replayable checkpoint.
  - Replay rejects unsupported phase.
  - Replay of supported phase creates derived output and lineage metadata.
  - Replay failure records telemetry and does not mutate the original session.

## Acceptance Criteria

- No operator surface implies step replay succeeded before execution exists.
- API behavior is explicit and tested for unsupported replay.
- If any replay path is implemented, it creates traceable derived output and does not corrupt original sessions.
- Replay documentation matches shipped behavior.

## Verification Commands

```bash
uv run pytest tests/test_web_server_session_routes.py tests/test_session_store.py tests/test_telemetry.py -x
cd dashboard && npx playwright test tests/e2e/decision-graph.spec.ts tests/e2e/content-gen-observability.spec.ts
```

## Risks

- Partial replay can be more dangerous than no replay if it mutates old sessions or hides invalidated downstream outputs. Prefer derived outputs and explicit lineage.
- Hiding replay may disappoint power users, but it avoids promising a workflow that is not implemented.
