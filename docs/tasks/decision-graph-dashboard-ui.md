# Decision Graph Dashboard UI Tasks

Status: Done

## Goal

Add a dedicated decision-graph visualization to the dashboard so operators can inspect causal chains and decision outcomes without overloading the existing workflow graph.

## Scope

- Add a separate decision-graph view
- Keep the current workflow graph unchanged
- Support selection, filtering, and explicit-versus-inferred differentiation

## Non-Goals

- Replacing the existing derived outputs panel
- Building advanced analytics like cross-run graph diffing in v1

## Task Breakdown

### 1. Add decision-graph types to the dashboard model

**Why**
The frontend needs a typed graph payload before a new view can be rendered safely.

**Work**
- Add `DecisionGraphNode`, `DecisionGraphEdge`, and `DecisionGraph`
- Add `decision_graph` to the session-detail response types
- Add a camelCase mapping if needed in the API client layer

**Acceptance criteria**
- Frontend type-checking passes
- The UI can receive graph data without using `any`

**Likely files**
- `dashboard/src/types/telemetry.ts`
- `dashboard/src/lib/api.ts`

### 2. Add a dedicated `DecisionGraph` component

**Why**
The current `WorkflowGraph` is built around session, phase, and agent nodes. It should not be stretched into a different product.

**Work**
- Create a new component under `dashboard/src/components/`
- Reuse the same rendering stack style as `workflow-graph.tsx` when practical
- Support:
  - click node to inspect source event
  - label and color by node kind
  - different styling for inferred edges
  - zoom and pan

**Acceptance criteria**
- Operators can inspect a graph node and jump to its backing event
- Graph remains readable on medium-sized sessions
- Explicit and inferred edges are visually distinct

**Likely files**
- new: `dashboard/src/components/decision-graph.tsx`
- `dashboard/src/components/workflow-graph.tsx` for reference only

### 3. Expose the decision graph in session details

**Why**
The session monitor is the natural place for graph exploration.

**Work**
- Add a new view mode or a new detail tab for the decision graph
- Keep the existing workflow graph, timeline, and table intact
- Wire graph-node selection back into the shared event inspector

**Recommended approach**
- Prefer a new `viewMode` entry such as `decision_graph`
- Use the right-side inspector for clicked nodes the same way other views already do

**Acceptance criteria**
- The graph can be opened for any session with derived outputs
- Selecting a node focuses the linked event in the inspector
- Existing views continue to work unchanged

**Likely files**
- `dashboard/src/components/session-details.tsx`
- `dashboard/src/types/telemetry.ts`

### 4. Add decision-specific filters

**Why**
Decision graphs get noisy quickly unless operators can narrow them.

**Work**
- Add graph-local or shared filters for:
  - decision type
  - actor
  - severity
  - explicit versus inferred
- Keep filtering simpler than the generic event filter system in v1

**Acceptance criteria**
- Operators can isolate one class of decisions without filtering away the whole session
- The filter model does not fight the existing telemetry filters

**Likely files**
- `dashboard/src/components/session-details.tsx`
- new helper module if needed under `dashboard/src/lib/`

### 5. Decide how the graph relates to the derived outputs panel

**Why**
The project already has a `Derived Outputs` panel showing decisions, issues, and cause-chain summaries.

**Work**
- Keep the current panel for summary inspection
- Add a link or shortcut from the panel into the graph view
- Avoid duplicating too much information between the summary list and graph

**Acceptance criteria**
- The summary panel and graph complement each other
- Operators do not need to choose between summary and deep inspection

**Likely files**
- `dashboard/src/components/derived-outputs-panel.tsx`
- `dashboard/src/components/session-details.tsx`

### 6. Add dashboard tests

**Why**
The graph UI will otherwise be easy to break while evolving filters or selection behavior.

**Work**
- Add tests for:
  - graph rendering with sample nodes and edges
  - inferred-edge styling
  - node click to inspector selection
  - empty-state behavior
- Add tests for any new view-mode state transitions

**Acceptance criteria**
- The graph renders correctly from typed session-detail data
- Selection and filtering behavior are pinned by tests

**Likely files**
- new frontend test files matching the dashboard test setup already in use
