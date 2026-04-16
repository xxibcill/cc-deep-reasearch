# P1-T2 - Add Operating Policy Metadata

## Objective

Make every operating phase explicitly runnable by adding typed governance fields instead of leaving stage rules implicit in prose.

## Scope

- add models for owner, max turnaround time, entry criteria, exit criteria, skip conditions, kill conditions, and reuse opportunities
- expose policy fields in `PipelineContext`, `StageTrace`, and managed briefs
- define how policy decisions and overrides are recorded during execution

## Affected Areas

- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/brief_service.py`
- `src/cc_deep_research/content_gen/storage/`
- `docs/content-generation.md`

## Dependencies

- P1-T1 must define the canonical phase taxonomy

## Acceptance Criteria

- typed operating policy metadata exists for every phase
- traces can record why a phase was skipped, killed, or time-boxed
- operator-facing docs explain how these fields are populated and reviewed
