# Task 004: Add Durable Step Checkpoints And Resume Execution

Status: Todo

## Objective

Make the research workflow restartable and debuggable at step granularity instead of only inspectable after the fact. This task should add durable checkpoints for major workflow steps so an operator or developer can:

- inspect the exact inputs and outputs of a step
- rerun one step without rerunning the entire workflow
- resume a failed or interrupted run from the latest valid checkpoint
- replay a completed run from a selected checkpoint for debugging

## Scope

- define a durable checkpoint contract for workflow steps and iterations
- persist checkpoint snapshots during active execution, not only at session end
- add resume metadata that records which checkpoint is safe to restart from
- add CLI and backend entrypoints to resume a run from a checkpoint or rerun one step in debug mode
- capture enough config, artifact, and dependency context to make step reruns reproducible
- keep checkpoint creation append-only and compatible with the trace bundle work from Task 003

## Required Checkpoint Capabilities

Each persisted checkpoint should include at least:

- `checkpoint_id`
- `session_id`
- `trace_version`
- `checkpoint_version`
- `sequence_number`
- `timestamp`
- `phase`
- `operation`
- `attempt`
- `status`
- `resume_token`
- `parent_checkpoint_id`
- `cause_event_id`
- `input_ref`
- `output_ref`
- `state_ref`
- `config_ref`
- `artifact_refs`
- `provider_fixture_refs`
- `replayable`
- `resume_safe`

## Checkpoint Boundaries

Persist checkpoints at minimum for:

- session start
- post-team initialization
- post-strategy analysis
- post-query expansion
- post-source collection
- post-analysis pass
- post-validation pass
- each iterative follow-up decision
- each iterative follow-up collection pass
- final session completion or interruption

For deep or iterative runs, the checkpoint contract must distinguish:

- phase-level checkpoints
- iteration-level checkpoints
- step reruns versus full-run resumes

## Resume And Rerun Semantics

Support at least these execution modes:

- `resume_latest`: continue a failed or interrupted run from the latest `resume_safe` checkpoint
- `resume_from_checkpoint`: continue a run from a specific checkpoint ID
- `rerun_step`: rerun one checkpointed operation with persisted inputs and current or pinned config
- `debug_replay`: execute from a checkpoint using recorded fixtures where available and clearly mark live fallbacks

The contract should define what is allowed to change between original execution and resume:

- config pinned exactly
- config patched with explicit override record
- live provider access allowed or disallowed
- artifact reuse allowed or forced rebuild

## API And CLI Work

Add or extend interfaces for:

- backend session detail responses to expose checkpoint inventory and latest resumable checkpoint
- a backend resume endpoint for checkpoint-based restart
- a backend debug-rerun endpoint for one checkpointed step
- CLI commands to list checkpoints, inspect one checkpoint, resume from checkpoint, and rerun a step
- trace bundle export to include checkpoint manifests and references

Recommended commands and endpoints:

- extend `GET /api/sessions/{session_id}`
- add `GET /api/sessions/{session_id}/checkpoints`
- add `POST /api/sessions/{session_id}/resume`
- add `POST /api/sessions/{session_id}/rerun-step`
- extend `ccdr session` with checkpoint-aware subcommands

## Persistence Work

Define a stable on-disk layout for checkpoint data, for example:

- `telemetry/<session_id>/events.jsonl`
- `telemetry/<session_id>/summary.json`
- `telemetry/<session_id>/checkpoints/<sequence>_<phase>_<operation>.json`
- `telemetry/<session_id>/checkpoints/manifest.json`

Each checkpoint payload should prefer references to large artifacts instead of inlining everything, but it must persist enough material to rebuild the exact step inputs later.

At minimum, persist or reference:

- normalized step inputs
- normalized step outputs
- relevant session-state snapshot
- config snapshot
- artifact paths and hashes
- provider response fixtures or explicit non-captured markers
- dependency versions needed for replay

## Target Files

- `src/cc_deep_research/monitoring.py`
- `src/cc_deep_research/orchestration/runtime.py`
- `src/cc_deep_research/orchestration/phases.py`
- `src/cc_deep_research/orchestration/execution.py`
- `src/cc_deep_research/orchestration/session_state.py`
- `src/cc_deep_research/session_store.py`
- `src/cc_deep_research/web_server.py`
- `src/cc_deep_research/cli/session.py`
- `src/cc_deep_research/telemetry/live.py`
- `src/cc_deep_research/telemetry/query.py`
- `src/cc_deep_research/research_runs/`
- `dashboard/src/types/telemetry.ts`
- `dashboard/src/lib/api.ts`
- `dashboard/src/components/session-details.tsx`

## Implementation Notes

- checkpointing should happen in Python orchestration code, not be reconstructed from frontend event streams
- treat checkpoints as immutable records; new resumes should append new events and new checkpoint lineage instead of mutating old files
- do not mark a checkpoint `resume_safe` until all required refs and hashes are persisted successfully
- separate observability from resumability: a rich event stream alone is not a checkpoint
- prefer stable normalized input/output envelopes over raw in-memory objects
- when a step cannot be replayed exactly, expose that explicitly with `replayable=false` and a machine-readable reason
- support partial capture first for high-value steps, but make unsupported steps visible instead of silently skipping them

## Acceptance Criteria

- active runs persist durable checkpoints at the defined workflow boundaries
- a failed or interrupted run exposes a latest safe resume point
- a developer can inspect one checkpoint and see step inputs, outputs, state snapshot, and artifact refs
- the backend or CLI can resume a run from a checkpoint without rerunning prior completed steps
- the backend or CLI can rerun one step in debug mode from persisted checkpoint inputs
- replay and resume paths clearly distinguish fixture-backed execution from live-provider execution
- exported trace bundles include checkpoint manifests and the refs needed for later replay tooling

## Suggested Verification

- add checkpoint persistence coverage in `tests/test_monitoring.py`
- add orchestration resume and rerun coverage in `tests/test_orchestrator.py`
- add API coverage in `tests/test_web_server.py`
- add CLI coverage for checkpoint list, inspect, and resume commands
- manually interrupt one run after source collection, resume it, and verify prior phases are not rerun
- manually rerun one analysis checkpoint with fixture-backed inputs and verify the new lineage is recorded

## Dependencies

- `trace_001_trace_contract_hardening.md`
- `trace_002_derived_trace_api_and_history.md`
- `trace_003_dashboard_compare_and_replay_foundation.md`

## Out Of Scope

- perfect deterministic replay for every provider and tool from day one
- cross-machine environment virtualization
- CI golden-trace regression policy
- full compare UX redesign beyond checkpoint visibility needed for debugging
