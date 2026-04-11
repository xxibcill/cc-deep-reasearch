# Resume Context Follow-up

Date: 2026-04-11
Status: Open
Priority: P2

## Finding

Resume jobs currently reuse the original `PipelineContext` object instead of cloning it.

- Route: `src/cc_deep_research/content_gen/router.py`
- Registry storage: `src/cc_deep_research/content_gen/progress.py`
- Affected flow: `POST /api/content-gen/pipelines/{pipeline_id}/resume`

## Why It Matters

The failed run and the resumed run can end up holding the same in-memory `PipelineContext`
instance. When the resumed run mutates `current_stage` or later stage outputs, the original
failed job's saved snapshot also changes in memory. That makes historical job state unstable
and can mislead operators during debugging or incident review.

## Reproduction Summary

1. Create a failed pipeline job with a saved `PipelineContext`.
2. Resume the pipeline.
3. Store the same `ctx` object on the new resume job.
4. Mutate the resumed context.
5. Observe the original failed job reflect the same mutation.

## Fix Direction

- Clone the context before attaching it to a resumed job.
- Prefer cloning on registry writes as well, so job snapshots are isolated by default.
- Add a regression test proving the original failed job does not change after resume progress.

## Notes

This is recorded for later implementation only. No runtime fix is included in this change.
