# Task 06: Enrich Pipeline Stage Trace Data For Operator Visibility

## Goal

Improve the trace payloads produced by the content-generation backend so the dashboard can show better decisions, warnings, and stage summaries without relying on brittle UI-side inference.

## Problem Statement

`PipelineStageTrace` currently carries `input_summary`, `output_summary`, `warnings`, and `decision_summary`, but many stages populate only basic strings. The UI can render those strings, but operators still lack good explanations for why a stage chose one artifact, degraded output, reused cached work, or stopped iterating.

## Files To Inspect

- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/orchestrator.py`
- stage agents under `src/cc_deep_research/content_gen/agents/` if needed
- `dashboard/src/types/content-gen.ts`
- `dashboard/src/components/content-gen/stage-trace-summary.tsx`

## Expected Deliverables

1. Extend `PipelineStageTrace` with a small set of structured fields that are broadly useful, for example:
   - selected artifact identifiers
   - numeric counts
   - degradation flags or reasons
   - cache reuse indicators
   - iteration or quality summary fields where relevant
2. Update the orchestrator to populate those fields for the stages where the information already exists.
3. Update the TypeScript mirror type definitions.
4. Update the trace summary UI to surface the new structured fields in a readable way.

## Constraints

- Keep the schema compact. Do not dump full stage outputs into traces.
- Do not encode important state only inside prose strings if it can be a stable field.
- Preserve backward compatibility where practical, or update all call sites together.

## Suggested High-Value Fields

- backlog/scoring:
  - selected idea id
  - shortlist count
  - degraded output flag
- angles:
  - selected angle id
  - option count
- research:
  - cache reused
  - fact/proof counts
- scripting:
  - step count
  - llm call count
  - final word count
- iterative loop:
  - current iteration
  - latest quality score
  - rerun research decision

## Acceptance Criteria

- Trace data becomes meaningfully richer for operators.
- The UI can show at least some of the new structured fields without parsing prose.
- Python and TypeScript models remain aligned.

## Test Plan

- Add model-level or orchestrator-level tests for new trace fields.
- Extend frontend tests if the UI starts rendering new trace metadata.

## Out Of Scope

- full artifact serialization inside traces
- large redesign of all stage models

