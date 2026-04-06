# Task 15: Improve Decision Graph Usability And Explainability

Status: Done

## Goal

Make the decision graph easier to understand and more actionable for operators who are not already deep in the telemetry schema.

## Depends On

- Tasks 01 through 14 complete

## Primary Areas

- `dashboard/src/components/decision-graph.tsx`
- `dashboard/src/components/session-details.tsx`
- `dashboard/src/components/telemetry/detail-inspector.tsx`
- `dashboard/src/lib/telemetry-transformers.ts`

## Problem To Solve

The decision graph is valuable but may still be too expert-only:

- node and edge meaning can be unclear
- filters exist, but interpretation still requires too much context
- explicit versus inferred links may not be obvious enough in use

## Required Changes

1. Improve graph affordances so operators understand what they are looking at faster.
2. Clarify the difference between:
   - explicit links
   - inferred links
   - high-severity decisions
3. Improve selection and inspection flow from graph node to detail view.
4. Add lightweight explanatory framing without turning the graph into documentation-heavy UI.

## Implementation Guidance

- Keep the graph exploratory and dense, not simplified into a toy view.
- Prefer legend, labeling, selection cues, and inspector improvements over removing information.
- Maintain current filter capabilities and integrate with them more clearly if needed.

## Out Of Scope

- new backend decision-graph fields
- replacing D3 with another library
- AI-generated graph explanations

## Acceptance Criteria

- A technically capable operator can understand the graph structure and significance faster than before.
- Node selection and detail inspection feel more direct.
- The graph remains useful for power users.

## Verification

- Manually test decision graph filtering, selection, and inspection.
- Check clarity with dense and sparse graphs.
