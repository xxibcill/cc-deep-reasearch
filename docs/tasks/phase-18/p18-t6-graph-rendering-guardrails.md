# P18-T6: Graph Rendering Guardrails

## Summary

Keep graph-heavy monitor views responsive by reducing unnecessary D3 redraws and adding large-session aggregation or drill-down behavior.

## Details

1. Profile `WorkflowGraph`, `DecisionGraph`, and `AgentTimeline` with large sessions.
2. Avoid full D3 teardown/redraw when only selected event or highlight state changes.
3. Preserve dynamic imports for graph-heavy components so non-graph monitor views do not pay their bundle and execution cost upfront.
4. Add large-session graph guardrails:
   - aggregate repeated phase and agent nodes
   - cap rendered nodes and edges when needed
   - provide drill-down or filtered expansion for dense sections
5. Make graph thresholds explicit constants with tests or documented rationale.
6. Verify graph interactions still support pan, zoom, click-to-inspect, selected-event highlighting, and empty states.

## Acceptance Criteria

- Switching into graph-heavy views is faster than the P18-T1 baseline for large sessions.
- Selected-event changes do not trigger full graph reconstruction.
- Very large sessions do not render unbounded SVG nodes and edges by default.
- Graph controls and click-to-inspect behavior remain functional.
- Playwright smoke coverage includes at least one graph view interaction.
