# Task P2-T2: Research Hypothesis Integration

## Objective

Ensure the research-pack stage tests the hypotheses defined during opportunity planning instead of starting from a loosely related theme alone.

## Scope

- Pass `research_hypotheses` from `OpportunityBrief` into research-pack prompts.
- Preserve which hypotheses were tested, supported, unsupported, or unresolved.
- Surface unsupported assumptions for later QC and scripting caution.

## Acceptance Criteria

- Research-pack generation explicitly references opportunity-stage hypotheses.
- The resulting artifact can distinguish supported from unsupported planning assumptions.
- Downstream stages can see which claims need caution or additional proof.

## Advice For The Smaller Coding Agent

- Keep the first version focused on hypothesis traceability, not on redesigning all research-pack outputs.
