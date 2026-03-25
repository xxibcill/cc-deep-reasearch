# Decision Graph Backend Derivation Tasks

## Goal

Add a first-class backend-derived `decision_graph` output for each session so the project can render decisions, causes, state transitions, degradations, and outcomes as a navigable graph instead of a flat list.

## Scope

- Define a stable decision-graph data contract
- Derive graph nodes and edges from existing telemetry events
- Keep explicit and inferred relationships separate
- Reuse existing telemetry events instead of inventing a separate storage system

## Non-Goals

- Replacing the existing workflow graph
- Solving telemetry coverage gaps entirely in this task
- Building run-to-run diffing in v1

## Task Breakdown

### 1. Add graph types to the telemetry contract

**Why**
The backend and frontend need a shared graph shape before new derived outputs can be added safely.

**Work**
- Add backend-facing graph structures for nodes, edges, and summary metadata
- Keep the shape JSON-first and easy to serialize
- Include explicit support for `inferred` relationships

**Recommended node kinds**
- `decision`
- `state_change`
- `degradation`
- `failure`
- `event`
- `outcome`

**Recommended edge kinds**
- `caused_by`
- `produced`
- `rejected`
- `mitigated_by`
- `led_to`

**Acceptance criteria**
- A single graph shape can be returned from live detail, historical detail, and trace bundles
- Nodes and edges have stable IDs
- The contract can express both explicit and inferred links

**Likely files**
- `src/cc_deep_research/telemetry/tree.py`
- `dashboard/src/types/telemetry.ts`

### 2. Implement `build_decision_graph(events)`

**Why**
The current derived outputs expose decisions as flat records. A dedicated graph builder is the missing core feature.

**Work**
- Add `build_decision_graph(events)` to the telemetry derivation layer
- Create nodes from:
  - `decision.made`
  - `state.changed`
  - `degradation.detected`
  - failure/error events
- Create edges from:
  - `cause_event_id`
  - `cause_event_ids`
  - `parent_event_id`
  - explicit chosen vs rejected options
- Only infer extra edges when there is a narrow, deterministic rule

**Acceptance criteria**
- Sessions with explicit decisions produce non-empty graph output
- Graph nodes point back to source telemetry event IDs where possible
- Explicit and inferred edges are distinguishable in the output

**Likely files**
- `src/cc_deep_research/telemetry/tree.py`

### 3. Decide the inference boundary up front

**Why**
Decision graphs become misleading if the system quietly guesses too much.

**Work**
- Document which edges are explicit versus inferred
- Keep inferred edges limited to a few cases, such as:
  - decision followed by directly caused state change
  - degradation followed by failure in same cause chain
  - rejected options attached to a decision node
- Avoid guessing across unrelated timestamps or same-phase proximity alone

**Acceptance criteria**
- Operators can tell when the graph is certain versus heuristic
- The initial implementation favors correctness over graph density

**Likely files**
- `src/cc_deep_research/telemetry/tree.py`
- `docs/TELEMETRY.md`

### 4. Extend the derived summary to include `decision_graph`

**Why**
The graph should be part of the same derived-output family as `decisions`, `state_changes`, and `critical_path`.

**Work**
- Add `decision_graph` to `build_derived_summary()`
- Preserve existing derived outputs unchanged
- Keep empty graph output cheap and stable when there is no data

**Acceptance criteria**
- `build_derived_summary()` always returns a `decision_graph` key
- Empty sessions return a valid empty graph shape, not `null`

**Likely files**
- `src/cc_deep_research/telemetry/tree.py`

### 5. Add derivation tests for graph construction

**Why**
This logic will be brittle without direct graph-focused tests.

**Work**
- Add tests for:
  - explicit decision with one cause event
  - decision with rejected options
  - state change produced by a decision
  - degradation and failure chain
  - mixed explicit and inferred edges
  - empty graph behavior

**Acceptance criteria**
- Tests pin graph node and edge counts
- Tests verify explicit versus inferred markers
- Tests verify stable source event IDs in graph nodes

**Likely files**
- `tests/test_telemetry.py`

