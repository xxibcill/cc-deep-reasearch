# P9-T4: Split content_gen/orchestrator.py into Per-Stage Orchestrators

## Summary

Decompose the 4,302-line `content_gen/orchestrator.py` into per-stage orchestrator classes.

## Details

### What to implement

1. **Analyze the 4,302-line orchestrator**:
   - Identify distinct stages: angle → thesis → argument_map → backlog → execution_brief → scripting → QC → visual → packaging → production → publish
   - Identify shared state and context objects passed between stages

2. **Create per-stage orchestrator modules**:
   - `content_gen/stages/angle.py` - Angle generation stage
   - `content_gen/stages/thesis.py` - Thesis development stage
   - `content_gen/stages/argument_map.py` - Argument mapping stage
   - `content_gen/stages/backlog.py` - Backlog creation stage
   - `content_gen/stages/execution_brief.py` - Execution brief stage
   - `content_gen/stages/scripting.py` - Scripting stage
   - `content_gen/stages/qc.py` - Quality control stage
   - `content_gen/stages/visual.py` - Visual generation stage
   - `content_gen/stages/packaging.py` - Packaging stage
   - `content_gen/stages/production.py` - Production stage
   - `content_gen/stages/publish.py` - Publish stage

3. **Create a `ContentGenPipeline`** coordinator:
   - Orchestrates flow between per-stage orchestrators
   - Manages shared context/state
   - Handles error recovery and retries

4. **Maintain backward compatibility**:
   - `content_gen/orchestrator.py` re-exports the new classes
   - Add deprecation warnings

### Exit criteria

- `content_gen/orchestrator.py` replaced with `content_gen/pipeline.py` and `content_gen/stages/` subpackage
- All existing pipeline calls still work via backward-compatible re-exports
- Tests pass
