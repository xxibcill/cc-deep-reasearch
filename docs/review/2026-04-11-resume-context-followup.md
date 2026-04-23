# Resume Context Follow-up

Date: 2026-04-11
Status: Completed
Priority: P2

## Finding

Resume jobs were reusing the original `PipelineContext` object instead of cloning it.

- Route: `src/cc_deep_research/content_gen/router.py`
- Registry storage: `src/cc_deep_research/content_gen/progress.py`
- Affected flow: `POST /api/content-gen/pipelines/{pipeline_id}/resume`

## Why It Matters

The failed run and the resumed run could end up holding the same in-memory `PipelineContext`
instance. When the resumed run mutated `current_stage` or later stage outputs, the original
failed job's saved snapshot also changed in memory. That made historical job state unstable
and could mislead operators during debugging or incident review.

## Reproduction Summary

1. Create a failed pipeline job with a saved `PipelineContext`.
2. Resume the pipeline.
3. Store the same `ctx` object on the new resume job.
4. Mutate the resumed context.
5. Observe the original failed job reflect the same mutation.

## Fix Applied

**router.py:581** — Clone the context before attaching it to the resumed job:
```python
job_registry.update_context(new_job.pipeline_id, ctx.model_copy(deep=True))
```

**progress.py:325** — Clone on every `update_context` write so callers who retain
a reference don't see subsequent mutations:
```python
job.pipeline_context = context.model_copy(deep=True)
```

**progress.py:270** — `mark_completed` also clones to protect the stored context
from callers who retain references.

**router.py:604** — `_stage_completed` callback clones before registry write to
prevent the orchestrator's live object from being stored.

## Test Added

`tests/test_web_server.py::test_resume_context_isolation_from_original_failed_job`
proves the original failed job's `current_stage` is unchanged after resume progress.
